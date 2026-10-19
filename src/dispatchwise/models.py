"""Domain models shared by the library and the HTTP API."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Location(BaseModel):
    model_config = ConfigDict(frozen=True)

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class Pharmacy(BaseModel):
    id: str
    location: Location
    stock: Dict[str, int] = Field(default_factory=dict, description="SKU -> units on hand")
    queue_length: int = Field(default=0, ge=0, description="Orders waiting to be prepared")

    @field_validator("stock")
    @classmethod
    def _non_negative_stock(cls, value: Dict[str, int]) -> Dict[str, int]:
        for sku, qty in value.items():
            if qty < 0:
                raise ValueError(f"stock for {sku!r} cannot be negative")
        return value


class Driver(BaseModel):
    id: str
    location: Location
    current_load: int = Field(default=0, ge=0, description="Orders already assigned")
    capacity: int = Field(default=5, ge=1, description="Maximum concurrent orders")

    @property
    def available(self) -> bool:
        return self.current_load < self.capacity


class OrderLine(BaseModel):
    sku: str
    quantity: int = Field(ge=1)


class Order(BaseModel):
    id: str
    customer: Location
    lines: List[OrderLine] = Field(min_length=1)

    def demand(self) -> Dict[str, int]:
        """Aggregate quantities per SKU (duplicate lines are summed)."""
        totals: Dict[str, int] = {}
        for line in self.lines:
            totals[line.sku] = totals.get(line.sku, 0) + line.quantity
        return totals


class CostWeights(BaseModel):
    """Weights of the assignment cost function.

    ``cost = distance * route_km * traffic + load * driver_load + queue * total_queue
    + pickup * (pickups - 1)``
    """

    distance: float = Field(default=1.0, ge=0)
    load: float = Field(default=2.0, ge=0)
    queue: float = Field(default=0.75, ge=0)
    pickup: float = Field(default=3.0, ge=0, description="Penalty per extra pickup stop")
    avg_speed_kmh: float = Field(default=30.0, gt=0)
    minutes_per_queued_order: float = Field(default=4.0, ge=0)


class Pickup(BaseModel):
    pharmacy_id: str
    items: Dict[str, int]


class CostBreakdown(BaseModel):
    route_km: float
    traffic_multiplier: float
    distance_cost: float
    load_cost: float
    queue_cost: float
    pickup_cost: float
    total: float


class Candidate(BaseModel):
    driver_id: str
    pickups: List[Pickup]
    cost: CostBreakdown
    eta_minutes: float


class DispatchPlan(BaseModel):
    order_id: str
    split: bool
    pickups: List[Pickup]
    driver_id: str
    route: List[str] = Field(description="Stop ids in visiting order, ending at 'customer'")
    cost: CostBreakdown
    eta_minutes: float
    alternatives: List[Candidate] = Field(default_factory=list)
    hour: Optional[int] = None
