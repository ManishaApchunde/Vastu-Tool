"""Low-level geometry helpers. Coordinates are image pixels: x to the right, y downward."""
import math

from shapely.geometry import Polygon
from shapely.validation import make_valid

Point = tuple[float, float]


class GeometryError(ValueError):
    """Raised when verified geometry can't be used for analysis."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def to_polygon(points: list, *, name: str = "shape") -> Polygon:
    if not points or len(points) < 3:
        raise GeometryError("invalid_geometry", f"{name} needs at least 3 corner points.")
    try:
        poly = Polygon([(float(x), float(y)) for x, y in points])
    except (TypeError, ValueError) as exc:
        raise GeometryError("invalid_geometry", f"{name} has malformed coordinates.") from exc
    if not poly.is_valid:
        fixed = make_valid(poly)
        # make_valid can return a collection; keep the largest polygon part
        parts = [g for g in getattr(fixed, "geoms", [fixed]) if g.geom_type == "Polygon"]
        if not parts:
            raise GeometryError("invalid_geometry", f"{name} crosses itself and can't be repaired.")
        poly = max(parts, key=lambda g: g.area)
    if poly.area < 1.0:
        raise GeometryError("invalid_geometry", f"{name} has no area.")
    return poly


def rotate_point(p: Point, origin: Point, degrees: float) -> Point:
    """Rotate visually clockwise by `degrees` in screen coordinates (y down)."""
    t = math.radians(degrees)
    dx, dy = p[0] - origin[0], p[1] - origin[1]
    return (origin[0] + dx * math.cos(t) - dy * math.sin(t), origin[1] + dx * math.sin(t) + dy * math.cos(t))


def rotate_points(points: list, origin: Point, degrees: float) -> list[Point]:
    return [rotate_point((x, y), origin, degrees) for x, y in points]


def bearing_from(centre: Point, p: Point) -> float:
    """Compass bearing (0 = North, 90 = East) of p from centre, in a North-up frame."""
    dx, dy = p[0] - centre[0], p[1] - centre[1]
    return (math.degrees(math.atan2(dx, -dy)) + 360.0) % 360.0


DIRECTIONS_8 = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def direction_8(bearing: float) -> str:
    return DIRECTIONS_8[int(((bearing + 22.5) % 360) // 45)]


def poly_coords(poly: Polygon) -> list[list[float]]:
    return [[round(x, 2), round(y, 2)] for x, y in list(poly.exterior.coords)[:-1]]
