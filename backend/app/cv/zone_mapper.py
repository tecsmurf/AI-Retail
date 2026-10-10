"""Zone assignment: map a normalized ground-contact point to one store zone.

Overlaps are resolved deterministically: highest ``priority`` first, then the
smallest polygon (the more specific zone), then the zone name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from app.cv.geometry import point_in_polygon, polygon_area, validate_polygon


@dataclass
class ZonePolygon:
    name: str
    zone_type: str
    polygon: List[Tuple[float, float]]  # normalized [0, 1] coordinates
    priority: int = 0
    zone_id: Optional[str] = None
    is_revenue_zone: bool = True
    color: str = "#4CAF50"
    area: float = field(init=False)

    def __post_init__(self) -> None:
        self.polygon = [(float(x), float(y)) for x, y in self.polygon]
        self.area = abs(polygon_area(self.polygon))


class InvalidZoneError(ValueError):
    pass


class ZoneMapper:
    def __init__(self, zones: Optional[Sequence[ZonePolygon]] = None, validate: bool = True) -> None:
        self.zones: List[ZonePolygon] = []
        for zone in zones or []:
            self.add_zone(zone, validate=validate)

    def add_zone(self, zone: ZonePolygon, validate: bool = True) -> None:
        if validate:
            problems = validate_polygon(zone.polygon)
            if problems:
                raise InvalidZoneError(f"Zone '{zone.name}': {'; '.join(problems)}")
        self.zones.append(zone)
        self.zones.sort(key=lambda z: (-z.priority, z.area, z.name))

    def get_zone(self, x: float, y: float) -> Optional[ZonePolygon]:
        for zone in self.zones:  # already in resolution order
            if point_in_polygon(x, y, zone.polygon):
                return zone
        return None

    def has_type(self, zone_type: str) -> bool:
        return any(z.zone_type == zone_type for z in self.zones)
