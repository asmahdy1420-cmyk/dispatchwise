from __future__ import annotations

import pytest

from conftest import loc, make_order
from dispatchwise import CostWeights, Driver, plan_dispatch
from dispatchwise.errors import NoDriverAvailableError


def test_single_pharmacy_plan_picks_closest_driver_and_pharmacy(customer, pharmacies, drivers):
    plan = plan_dispatch(make_order(customer, A=1), pharmacies, drivers, hour=10)
    assert not plan.split
    assert plan.pickups[0].pharmacy_id == "near"
    assert plan.driver_id == "d-close"
    assert plan.route == ["d-close", "near", "customer"]
    assert plan.cost.total == pytest.approx(
        plan.cost.distance_cost + plan.cost.load_cost + plan.cost.queue_cost, abs=1e-2
    )
    assert plan.alternatives and all(a.cost.total >= plan.cost.total for a in plan.alternatives)


def test_split_order_plan(customer, drivers):
    from dispatchwise.models import Pharmacy

    pharmacies = [
        Pharmacy(id="a", location=loc(25.29, 51.53), stock={"A": 2}),
        Pharmacy(id="b", location=loc(25.30, 51.54), stock={"B": 2}),
    ]
    plan = plan_dispatch(make_order(customer, A=1, B=1), pharmacies, drivers, hour=10)
    assert plan.split
    assert {p.pharmacy_id for p in plan.pickups} == {"a", "b"}
    assert plan.cost.pickup_cost == CostWeights().pickup
    assert plan.route[0] == plan.driver_id and plan.route[-1] == "customer"


def test_busy_driver_loses_to_idle_one(customer, pharmacies):
    drivers = [
        Driver(id="busy", location=loc(25.2900, 51.5310), current_load=4, capacity=5),
        Driver(id="idle", location=loc(25.2800, 51.5310), current_load=0),
    ]
    plan = plan_dispatch(
        make_order(customer, A=1),
        pharmacies,
        drivers,
        hour=10,
        weights=CostWeights(load=5.0),
    )
    assert plan.driver_id == "idle"


def test_queue_weight_can_move_order_to_quieter_pharmacy(customer, pharmacies, drivers):
    pharmacies[0].queue_length = 30  # "near" is swamped
    plan = plan_dispatch(make_order(customer, B=1), pharmacies, drivers, hour=10)
    assert plan.pickups[0].pharmacy_id == "mid"


def test_rush_hour_increases_cost_and_eta(customer, pharmacies, drivers):
    order = make_order(customer, A=1)
    night = plan_dispatch(order, pharmacies, drivers, hour=3)
    rush = plan_dispatch(order, pharmacies, drivers, hour=18)
    assert rush.cost.traffic_multiplier > night.cost.traffic_multiplier
    assert rush.eta_minutes > night.eta_minutes
    assert rush.cost.total > night.cost.total


def test_full_drivers_are_skipped_and_none_available_raises(customer, pharmacies):
    full = Driver(id="full", location=customer, current_load=5, capacity=5)
    with pytest.raises(NoDriverAvailableError):
        plan_dispatch(make_order(customer, A=1), pharmacies, [full], hour=10)


def test_invalid_hour_rejected(customer, pharmacies, drivers):
    with pytest.raises(ValueError):
        plan_dispatch(make_order(customer, A=1), pharmacies, drivers, hour=24)
