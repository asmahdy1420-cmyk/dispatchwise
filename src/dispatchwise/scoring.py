"""Weighted cost of a (driver, pickups) assignment."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Mapping, Tuple

from dispatchwise.geo import nearest_neighbour_order, path_length_km
from dispatchwise.models import Candidate, CostBreakdown

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dispatchwise.models import CostWeights, Driver, Location, Pharmacy, Pickup
    from dispatchwise.traffic import TrafficProfile


def score_candidate(
    driver: Driver,
    pickups: Sequence[Pickup],
    pharmacies: Mapping[str, Pharmacy],
    customer: Location,
    hour: int,
    weights: CostWeights,
    traffic: TrafficProfile,
) -> Tuple[Candidate, List[str]]:
    """Score one assignment and return it with its stop order.

    Route: driver -> pickups (nearest-neighbour order) -> customer.
    """
    stops = [pharmacies[p.pharmacy_id] for p in pickups]
    visit = nearest_neighbour_order(driver.location, [s.location for s in stops])
    ordered = [stops[i] for i in visit]
    route_km = path_length_km([driver.location, *[s.location for s in ordered], customer])

    multiplier = traffic.multiplier(hour)
    total_queue = sum(s.queue_length for s in ordered)

    distance_cost = weights.distance * route_km * multiplier
    load_cost = weights.load * driver.current_load
    queue_cost = weights.queue * total_queue
    pickup_cost = weights.pickup * max(0, len(ordered) - 1)
    total = distance_cost + load_cost + queue_cost + pickup_cost

    drive_minutes = route_km / weights.avg_speed_kmh * 60 * multiplier
    # Pharmacies prepare in parallel once notified, so the slowest queue dominates.
    prep_minutes = max(s.queue_length for s in ordered) * weights.minutes_per_queued_order
    eta = drive_minutes + prep_minutes

    candidate = Candidate(
        driver_id=driver.id,
        pickups=[pickups[i] for i in visit],
        cost=CostBreakdown(
            route_km=round(route_km, 3),
            traffic_multiplier=multiplier,
            distance_cost=round(distance_cost, 3),
            load_cost=round(load_cost, 3),
            queue_cost=round(queue_cost, 3),
            pickup_cost=round(pickup_cost, 3),
            total=round(total, 3),
        ),
        eta_minutes=round(eta, 1),
    )
    return candidate, [s.id for s in ordered]
