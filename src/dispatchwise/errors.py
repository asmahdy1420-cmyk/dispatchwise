"""Exceptions raised by the planner."""

from __future__ import annotations

from typing import Dict


class DispatchError(Exception):
    """Base class for planning failures."""


class UnfulfillableOrderError(DispatchError):
    """The combined stock of all pharmacies cannot cover the order."""

    def __init__(self, order_id: str, shortfall: Dict[str, int]) -> None:
        self.order_id = order_id
        self.shortfall = shortfall
        missing = ", ".join(f"{sku} x{qty}" for sku, qty in sorted(shortfall.items()))
        super().__init__(f"order {order_id} cannot be fulfilled; short of: {missing}")


class NoDriverAvailableError(DispatchError):
    """Every driver is at capacity."""
