"""Great-circle distance helpers."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dispatchwise.models import Location

EARTH_RADIUS_KM = 6371.0088


def haversine_km(a: Location, b: Location) -> float:
    """Return the great-circle distance between two points in kilometres."""
    lat1, lon1 = math.radians(a.lat), math.radians(a.lon)
    lat2, lon2 = math.radians(b.lat), math.radians(b.lon)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(h)))


def path_length_km(points: Sequence[Location]) -> float:
    """Total length of a path visiting ``points`` in order."""
    return sum(haversine_km(points[i], points[i + 1]) for i in range(len(points) - 1))


def nearest_neighbour_order(start: Location, stops: Sequence[Location]) -> list[int]:
    """Order ``stops`` greedily by nearest neighbour from ``start``.

    Returns the indices of ``stops`` in visiting order. For the handful of
    pickups a split order produces (usually 2-3) this is optimal or very close.
    """
    remaining = list(range(len(stops)))
    order: list[int] = []
    current = start
    while remaining:
        nxt = min(remaining, key=lambda i: haversine_km(current, stops[i]))
        order.append(nxt)
        remaining.remove(nxt)
        current = stops[nxt]
    return order
