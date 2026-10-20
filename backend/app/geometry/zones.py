"""Zone systems. A zone system divides the North-up bounding box of the plan into named zones.

Only the 3x3 grid is implemented for the MVP. A 16-zone (22.5 degree sectors) or 32-zone system
can be added by subclassing ZoneSystem and registering it; nothing else needs to change."""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from shapely.geometry import Polygon, box


@dataclass(frozen=True)
class ZoneCell:
    code: str
    name: str
    polygon: Polygon  # North-up frame


ZONE_NAMES = {
    "N": "North", "NE": "North-East", "E": "East", "SE": "South-East", "S": "South",
    "SW": "South-West", "W": "West", "NW": "North-West", "C": "Centre (Brahmasthan)",
}


class ZoneSystem(ABC):
    code: str
    label: str

    @abstractmethod
    def build(self, frame: Polygon) -> list[ZoneCell]:
        """Divide the North-up plan frame into zones."""


class Grid3x3(ZoneSystem):
    code = "grid_3x3"
    label = "3 x 3 grid (8 directions + centre)"
    # rows top→bottom (North at top), cols left→right (West at left)
    LAYOUT = [["NW", "N", "NE"], ["W", "C", "E"], ["SW", "S", "SE"]]

    def build(self, frame: Polygon) -> list[ZoneCell]:
        minx, miny, maxx, maxy = frame.bounds
        w, h = (maxx - minx) / 3.0, (maxy - miny) / 3.0
        cells = []
        for r, row in enumerate(self.LAYOUT):
            for c, code in enumerate(row):
                cell = box(minx + c * w, miny + r * h, minx + (c + 1) * w, miny + (r + 1) * h)
                cells.append(ZoneCell(code, ZONE_NAMES[code], cell))
        return cells


ZONE_SYSTEMS: dict[str, ZoneSystem] = {Grid3x3.code: Grid3x3()}


def get_zone_system(code: str) -> ZoneSystem:
    try:
        return ZONE_SYSTEMS[code]
    except KeyError as exc:
        raise ValueError(f"Unknown zone system '{code}'. Available: {sorted(ZONE_SYSTEMS)}") from exc
