"""Decide which pharmacies an order is picked up from.

The problem is a weighted, multi-unit set cover: choose the fewest pharmacies
whose combined stock covers every requested unit, preferring pharmacies close
to the customer. Exact set cover is NP-hard; the classic greedy rule ("take
the set covering the most uncovered units") is within a ln(n) factor of
optimal and, for the 1-3 pickups real orders need, almost always optimal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

from dispatchwise.errors import UnfulfillableOrderError
from dispatchwise.geo import haversine_km
from dispatchwise.models import Pickup

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dispatchwise.models import Order, Pharmacy


def can_fulfil(pharmacy: Pharmacy, demand: Dict[str, int]) -> bool:
    return all(pharmacy.stock.get(sku, 0) >= qty for sku, qty in demand.items())


def single_source_pharmacies(order: Order, pharmacies: Sequence[Pharmacy]) -> List[Pharmacy]:
    """Pharmacies that can fulfil the whole order alone, nearest first."""
    demand = order.demand()
    matches = [p for p in pharmacies if can_fulfil(p, demand)]
    return sorted(matches, key=lambda p: haversine_km(p.location, order.customer))


def shortfall(order: Order, pharmacies: Sequence[Pharmacy]) -> Dict[str, int]:
    """Units per SKU that no combination of pharmacies can supply."""
    missing: Dict[str, int] = {}
    for sku, qty in order.demand().items():
        available = sum(p.stock.get(sku, 0) for p in pharmacies)
        if available < qty:
            missing[sku] = qty - available
    return missing


def split_order(
    order: Order,
    pharmacies: Sequence[Pharmacy],
    max_pickups: Optional[int] = None,
) -> List[Pickup]:
    """Greedy set cover: fewest pickups first, then shortest distance to customer.

    Raises ``UnfulfillableOrderError`` when the network is short of stock or the
    cover needs more than ``max_pickups`` stops.
    """
    missing = shortfall(order, pharmacies)
    if missing:
        raise UnfulfillableOrderError(order.id, missing)

    remaining = order.demand()
    pool = list(pharmacies)
    chosen: List[Pharmacy] = []

    def covered_units(pharmacy: Pharmacy) -> int:
        return sum(min(pharmacy.stock.get(sku, 0), qty) for sku, qty in remaining.items())

    while remaining:
        best = min(
            pool,
            key=lambda p: (
                -covered_units(p),
                haversine_km(p.location, order.customer),
                p.queue_length,
                p.id,
            ),
        )
        for sku, qty in list(remaining.items()):
            take = min(best.stock.get(sku, 0), qty)
            if take == qty:
                del remaining[sku]
            elif take:
                remaining[sku] = qty - take
        chosen.append(best)
        pool.remove(best)

    pickups = consolidate(order, chosen)

    if max_pickups is not None and len(pickups) > max_pickups:
        raise UnfulfillableOrderError(order.id, remaining_after(order, pickups[:max_pickups]))
    return pickups


def remaining_after(order: Order, pickups: Sequence[Pickup]) -> Dict[str, int]:
    """Demand left uncovered by ``pickups``."""
    left = order.demand()
    for pickup in pickups:
        for sku, qty in pickup.items.items():
            left[sku] = left.get(sku, 0) - qty
    return {sku: qty for sku, qty in left.items() if qty > 0}


def consolidate(order: Order, chosen: Sequence[Pharmacy]) -> List[Pickup]:
    """Re-allocate SKUs within the chosen pharmacies so each SKU is split as little as possible.

    The greedy pass decides *which* pharmacies to visit; it can still split a
    single SKU across two of them (1 box here, 1 box there) when one of them
    could supply the full quantity. Packers prefer whole lines, so each SKU
    goes to the closest chosen pharmacy that holds the full quantity, falling
    back to filling in greedy order. Pickups left empty are dropped.
    """
    ranked = sorted(chosen, key=lambda p: haversine_km(p.location, order.customer))
    allocation: Dict[str, Dict[str, int]] = {p.id: {} for p in chosen}
    for sku, qty in order.demand().items():
        whole = next((p for p in ranked if p.stock.get(sku, 0) >= qty), None)
        if whole is not None:
            allocation[whole.id][sku] = qty
            continue
        left = qty
        for pharmacy in chosen:
            take = min(pharmacy.stock.get(sku, 0), left)
            if take:
                allocation[pharmacy.id][sku] = take
                left -= take
            if not left:
                break
    return [Pickup(pharmacy_id=p.id, items=allocation[p.id]) for p in chosen if allocation[p.id]]
