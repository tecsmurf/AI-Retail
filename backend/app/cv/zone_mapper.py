"""Zone Intelligence — Map positions to business zones using point-in-polygon."""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class ZonePolygon:
    name: str
    zone_type: str
    polygon: List[Tuple[float, float]]
    is_revenue_zone: bool = True
    color: str = "#4CAF50"


class ZoneMapper:
    def __init__(self, zones: List[ZonePolygon] = None):
        self.zones = zones or []

    def add_zone(self, zone: ZonePolygon):
        self.zones.append(zone)

    def get_zone(self, x: float, y: float) -> Optional[ZonePolygon]:
        for zone in self.zones:
            if self._pip(x, y, zone.polygon):
                return zone
        return None

    @staticmethod
    def _pip(x: float, y: float, poly: List[Tuple[float, float]]) -> bool:
        n = len(poly)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = poly[i]
            xj, yj = poly[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside
