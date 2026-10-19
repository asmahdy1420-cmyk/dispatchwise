"""Top-level planner: split decision + driver assignment."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from dispatchwise.errors import DispatchError, NoDriverAvailableError, UnfulfillableOrderError
from dispatchwise.models import CostWeights, DispatchPlan, Pickup
from dispatchwise.scoring import score_candidate
from dispatchwise.splitting import single_source_pharmacies, split_order
from dispatchwise.traffic import TrafficProfile

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dispatchwise.models import Driver, Order, Pharmacy

__all__ = [
    "DispatchError",
    "NoDriverAvailableError",
    "UnfulfillableOrderError",
    "plan_dispatch",
]


def plan_dispatch(
    order: Order,
    pharmacies: Sequence[Pharmacy],
    drivers: Sequence[Driver],
    hour: Optional[int] = None,
    weights: Optional[CostWeights] = None,
    traffic: Optional[TrafficProfile] = None,
    max_pickups: Optional[int] = None,
    max_alternatives: int = 3,
) -> DispatchPlan:
    """Choose pickups and a driver for ``order`` at minimum weighted cost.

    1. If one or more pharmacies can fulfil the order alone, each is a
       candidate pickup set (no split).
    2. Otherwise a greedy set cover produces a split pickup set.
    3. Every pickup set is scored against every driver with spare capacity;
       the cheapest assignment wins and the next ones are returned as
       alternatives.
    """
    weights = weights or CostWeights()
    traffic = traffic or TrafficProfile()
    hour = datetime.now().hour if hour is None else hour
    if not 0 <= hour <= 23:
        raise ValueError(f"hour must be in 0..23, got {hour}")

    available = [d for d in drivers if d.available]
    if not available:
        raise NoDriverAvailableError("every driver is at capacity")

    demand = order.demand()
    singles = single_source_pharmacies(order, pharmacies)
    if singles:
        options: List[List[Pickup]] = [
            [Pickup(pharmacy_id=p.id, items=dict(demand))] for p in singles
        ]
    else:
        options = [split_order(order, pharmacies, max_pickups=max_pickups)]

    by_id = {p.id: p for p in pharmacies}
    scored = []
    for pickups in options:
        for driver in available:
            candidate, route = score_candidate(
                driver, pickups, by_id, order.customer, hour, weights, traffic
            )
            scored.append((candidate.cost.total, candidate.driver_id, candidate, route))
    scored.sort(key=lambda row: (row[0], row[1]))

    _, _, best, route = scored[0]
    return DispatchPlan(
        order_id=order.id,
        split=len(best.pickups) > 1,
        pickups=best.pickups,
        driver_id=best.driver_id,
        route=[best.driver_id, *route, "customer"],
        cost=best.cost,
        eta_minutes=best.eta_minutes,
        alternatives=[row[2] for row in scored[1 : 1 + max_alternatives]],
        hour=hour,
    )
