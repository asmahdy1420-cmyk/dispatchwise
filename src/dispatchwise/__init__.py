"""dispatchwise: multi-location pharmacy order dispatch optimiser."""

from __future__ import annotations

from dispatchwise.dispatcher import UnfulfillableOrderError, plan_dispatch
from dispatchwise.geo import haversine_km
from dispatchwise.models import (
    CostWeights,
    DispatchPlan,
    Driver,
    Location,
    Order,
    OrderLine,
    Pharmacy,
    Pickup,
)
from dispatchwise.splitting import split_order
from dispatchwise.traffic import TrafficProfile

__all__ = [
    "CostWeights",
    "DispatchPlan",
    "Driver",
    "Location",
    "Order",
    "OrderLine",
    "Pharmacy",
    "Pickup",
    "TrafficProfile",
    "UnfulfillableOrderError",
    "haversine_km",
    "plan_dispatch",
    "split_order",
]

__version__ = "0.1.0"
