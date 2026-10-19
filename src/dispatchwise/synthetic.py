"""Seeded synthetic scenarios for demos and tests."""

from __future__ import annotations

import math
import random
from typing import List, Optional

from pydantic import BaseModel

from dispatchwise.models import Driver, Location, Order, OrderLine, Pharmacy

DOHA = Location(lat=25.2854, lon=51.5310)


class Scenario(BaseModel):
    pharmacies: List[Pharmacy]
    drivers: List[Driver]
    orders: List[Order]


def _jitter(rng: random.Random, centre: Location, radius_km: float) -> Location:
    """Uniform point in a disc of ``radius_km`` around ``centre``."""
    r = radius_km * math.sqrt(rng.random())
    theta = rng.uniform(0, 2 * math.pi)
    dlat = (r * math.cos(theta)) / 111.32
    dlon = (r * math.sin(theta)) / (111.32 * math.cos(math.radians(centre.lat)))
    return Location(lat=round(centre.lat + dlat, 6), lon=round(centre.lon + dlon, 6))


def generate_scenario(
    n_pharmacies: int = 8,
    n_drivers: int = 6,
    n_orders: int = 200,
    n_skus: int = 25,
    n_hotspots: int = 4,
    radius_km: float = 12.0,
    centre: Optional[Location] = None,
    seed: int = 42,
) -> Scenario:
    """Build a reproducible city: pharmacies, drivers and clustered orders.

    Orders are drawn around ``n_hotspots`` neighbourhoods so clustering has
    real structure to find. Stock is sparse on purpose so some orders must
    be split across pharmacies.
    """
    rng = random.Random(seed)
    centre = centre or DOHA
    skus = [f"SKU-{i:03d}" for i in range(1, n_skus + 1)]

    pharmacies = []
    for i in range(1, n_pharmacies + 1):
        carried = rng.sample(skus, k=max(1, int(n_skus * rng.uniform(0.35, 0.7))))
        pharmacies.append(
            Pharmacy(
                id=f"PH-{i:02d}",
                location=_jitter(rng, centre, radius_km),
                stock={sku: rng.randint(1, 20) for sku in carried},
                queue_length=rng.randint(0, 8),
            )
        )

    drivers = [
        Driver(
            id=f"DR-{i:02d}",
            location=_jitter(rng, centre, radius_km),
            current_load=rng.randint(0, 3),
            capacity=4,
        )
        for i in range(1, n_drivers + 1)
    ]

    hotspots = [_jitter(rng, centre, radius_km * 0.8) for _ in range(n_hotspots)]
    orders = []
    for i in range(1, n_orders + 1):
        spot = rng.choice(hotspots)
        lines = [
            OrderLine(sku=sku, quantity=rng.randint(1, 3))
            for sku in rng.sample(skus, k=rng.randint(1, 4))
        ]
        orders.append(
            Order(id=f"ORD-{i:04d}", customer=_jitter(rng, spot, radius_km * 0.15), lines=lines)
        )
    return Scenario(pharmacies=pharmacies, drivers=drivers, orders=orders)
