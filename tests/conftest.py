from __future__ import annotations

import pytest

from dispatchwise.models import Driver, Location, Order, OrderLine, Pharmacy


def loc(lat: float, lon: float) -> Location:
    return Location(lat=lat, lon=lon)


@pytest.fixture
def customer() -> Location:
    return loc(25.2854, 51.5310)


@pytest.fixture
def pharmacies() -> list[Pharmacy]:
    # Positions are offsets from the customer: ~1 km, ~3 km and ~6 km away.
    return [
        Pharmacy(id="near", location=loc(25.2944, 51.5310), stock={"A": 5, "B": 1}),
        Pharmacy(id="mid", location=loc(25.3124, 51.5310), stock={"B": 10, "C": 4}),
        Pharmacy(id="far", location=loc(25.3394, 51.5310), stock={"A": 10, "B": 10, "C": 10}),
    ]


@pytest.fixture
def drivers() -> list[Driver]:
    return [
        Driver(id="d-close", location=loc(25.2900, 51.5310), current_load=0),
        Driver(id="d-away", location=loc(25.2000, 51.4500), current_load=0),
    ]


def make_order(customer: Location, **items: int) -> Order:
    return Order(
        id="o-1",
        customer=customer,
        lines=[OrderLine(sku=sku, quantity=qty) for sku, qty in items.items()],
    )
