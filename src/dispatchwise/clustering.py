"""Demand-zone clustering for pre-positioning idle drivers.

Requires the optional ``clustering`` extra (scikit-learn + numpy).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Dict, List, Optional

from pydantic import BaseModel

from dispatchwise.geo import haversine_km
from dispatchwise.models import Location

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dispatchwise.models import Driver


class DemandZone(BaseModel):
    zone_id: int
    centre: Location
    order_count: int
    share: float


class Positioning(BaseModel):
    driver_id: str
    zone_id: int
    target: Location
    distance_km: float


def _require_sklearn():
    try:
        import numpy as np
        from sklearn.cluster import KMeans
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            "demand-zone clustering needs the optional extra: "
            "pip install 'dispatchwise[clustering]'"
        ) from exc
    return np, KMeans


def demand_zones(
    points: Sequence[Location], k: int, random_state: Optional[int] = 0
) -> List[DemandZone]:
    """Cluster historical order coordinates into ``k`` demand zones.

    Coordinates are projected to a local equirectangular plane (longitude
    scaled by cos(mean latitude)) so Euclidean KMeans approximates ground
    distance at city scale. Zones are returned largest first.
    """
    if k < 1:
        raise ValueError("k must be >= 1")
    if len(points) < k:
        raise ValueError(f"need at least k={k} points, got {len(points)}")
    np, KMeans = _require_sklearn()

    lat0 = math.radians(sum(p.lat for p in points) / len(points))
    scale = math.cos(lat0)
    xy = np.array([[p.lon * scale, p.lat] for p in points], dtype=float)

    model = KMeans(n_clusters=k, n_init=10, random_state=random_state).fit(xy)
    counts = np.bincount(model.labels_, minlength=k)
    total = int(counts.sum())

    zones = [
        DemandZone(
            zone_id=i,
            centre=Location(lat=float(c[1]), lon=float(c[0] / scale)),
            order_count=int(counts[i]),
            share=round(int(counts[i]) / total, 4),
        )
        for i, c in enumerate(model.cluster_centers_)
    ]
    zones.sort(key=lambda z: (-z.order_count, z.zone_id))
    return zones


def allocate_drivers(zones: Sequence[DemandZone], n_drivers: int) -> Dict[int, int]:
    """Split ``n_drivers`` across zones in proportion to demand (largest remainder)."""
    if not zones:
        return {}
    total = sum(z.order_count for z in zones) or 1
    quotas = {z.zone_id: n_drivers * z.order_count / total for z in zones}
    alloc = {zid: int(q) for zid, q in quotas.items()}
    leftover = n_drivers - sum(alloc.values())
    for zid in sorted(quotas, key=lambda z: quotas[z] - alloc[z], reverse=True)[:leftover]:
        alloc[zid] += 1
    return alloc


def suggest_positioning(
    zones: Sequence[DemandZone], drivers: Sequence[Driver]
) -> List[Positioning]:
    """Send idle drivers (load 0) to zone centres, closest pairs first."""
    idle = [d for d in drivers if d.current_load == 0]
    slots = allocate_drivers(zones, len(idle))
    centre = {z.zone_id: z.centre for z in zones}

    pairs = sorted(
        (haversine_km(d.location, centre[zid]), d.id, zid) for d in idle for zid in centre
    )
    placed: List[Positioning] = []
    used = set()
    for dist, driver_id, zid in pairs:
        if driver_id in used or slots.get(zid, 0) == 0:
            continue
        used.add(driver_id)
        slots[zid] -= 1
        placed.append(
            Positioning(
                driver_id=driver_id,
                zone_id=zid,
                target=centre[zid],
                distance_km=round(dist, 3),
            )
        )
    return placed
