"""Geometry engine: verified plan + North angle -> centre, zones and zone membership.

Pipeline:
  1. centre = centroid of the verified outer boundary (the Brahmasthan point)
  2. rotate everything about the centre by -north_angle so true North points up
  3. build the zone grid on the North-up bounding box of the boundary
  4. assign each room to the zone it overlaps most, openings to the zone containing them
  5. rotate zone polygons back to image coordinates for display
"""
from dataclasses import dataclass, field

from shapely.geometry import Point as SPoint
from shapely.geometry import Polygon

from app.geometry.primitives import (
    GeometryError,
    bearing_from,
    direction_8,
    poly_coords,
    rotate_points,
    to_polygon,
)
from app.geometry.zones import get_zone_system


@dataclass
class RoomInput:
    id: str
    label: str
    room_type: str
    polygon: list


@dataclass
class OpeningInput:
    id: str
    kind: str
    is_main_entrance: bool
    position: list


@dataclass
class PlanInput:
    boundary: list
    rooms: list[RoomInput]
    openings: list[OpeningInput] = field(default_factory=list)


@dataclass
class ZoneOut:
    code: str
    name: str
    polygon: list  # image coordinates
    coverage: float


@dataclass
class RoomZoneOut:
    id: str
    label: str
    room_type: str
    primary_zone: str
    direction: str
    bearing_deg: float
    overlaps: dict[str, float]  # zone code -> fraction of room area
    area_fraction: float  # room area / plan area


@dataclass
class OpeningZoneOut:
    id: str
    kind: str
    is_main_entrance: bool
    zone: str
    direction: str


@dataclass
class ZoneResult:
    system: str
    north_angle: float
    centre: tuple[float, float]
    plan_area: float
    zones: list[ZoneOut]
    rooms: list[RoomZoneOut]
    openings: list[OpeningZoneOut]

    def zone_coverage(self, code: str) -> float | None:
        return next((z.coverage for z in self.zones if z.code == code), None)


def normalise_angle(angle: float) -> float:
    return float(angle) % 360.0


def compute_centre(boundary: list) -> tuple[float, float]:
    poly = to_polygon(boundary, name="Plan boundary")
    c = poly.centroid
    return (round(c.x, 2), round(c.y, 2))


def compute_zones(plan: PlanInput, north_angle: float, system: str = "grid_3x3") -> ZoneResult:
    north_angle = normalise_angle(north_angle)
    boundary = to_polygon(plan.boundary, name="Plan boundary")
    if not plan.rooms:
        raise GeometryError("missing_rooms", "Add at least one room before calculating zones.")

    centre = (boundary.centroid.x, boundary.centroid.y)
    # rotate by -north_angle so true North points to the top of the frame
    rot = -north_angle
    b_up = Polygon(rotate_points(list(boundary.exterior.coords)[:-1], centre, rot))
    cells = get_zone_system(system).build(b_up)

    zones = []
    for cell in cells:
        covered = cell.polygon.intersection(b_up).area / cell.polygon.area if cell.polygon.area else 0
        img_poly = Polygon(rotate_points(list(cell.polygon.exterior.coords)[:-1], centre, north_angle))
        zones.append(ZoneOut(cell.code, cell.name, poly_coords(img_poly), round(covered, 4)))

    rooms_out = []
    for room in plan.rooms:
        poly = to_polygon(room.polygon, name=f"Room '{room.label}'")
        up = Polygon(rotate_points(list(poly.exterior.coords)[:-1], centre, rot))
        overlaps = {}
        for cell in cells:
            a = up.intersection(cell.polygon).area
            if a > 0:
                overlaps[cell.code] = round(a / up.area, 4)
        if overlaps:
            primary = max(overlaps, key=overlaps.get)
        else:  # room drawn outside the plan frame: nearest cell
            primary = min(cells, key=lambda c: c.polygon.distance(up)).code
        b = bearing_from(centre, (up.centroid.x, up.centroid.y))
        rooms_out.append(
            RoomZoneOut(
                room.id, room.label, room.room_type, primary,
                "C" if primary == "C" else direction_8(b), round(b, 1), overlaps,
                round(poly.area / boundary.area, 4),
            )
        )

    openings_out = []
    for op in plan.openings:
        (px, py), = rotate_points([op.position], centre, rot)
        pt = SPoint(px, py)
        cell = next((c for c in cells if c.polygon.covers(pt)), None)
        code = cell.code if cell else min(cells, key=lambda c: c.polygon.distance(pt)).code
        openings_out.append(
            OpeningZoneOut(op.id, op.kind, op.is_main_entrance, code, direction_8(bearing_from(centre, (px, py))))
        )

    return ZoneResult(
        system=system,
        north_angle=north_angle,
        centre=(round(centre[0], 2), round(centre[1], 2)),
        plan_area=boundary.area,
        zones=zones,
        rooms=rooms_out,
        openings=openings_out,
    )


def boundary_from_rooms(room_polygons: list[list]) -> list[list[float]]:
    """Fallback outer boundary when the user didn't draw one: hull of all rooms."""
    from shapely.ops import unary_union

    polys = [to_polygon(p, name="Room") for p in room_polygons]
    if not polys:
        raise GeometryError("missing_rooms", "Add at least one room.")
    merged = unary_union(polys)
    shape = merged if merged.geom_type == "Polygon" and merged.interiors == [] else merged.convex_hull
    if shape.geom_type != "Polygon":
        shape = merged.convex_hull
    return poly_coords(shape.simplify(1.0))
