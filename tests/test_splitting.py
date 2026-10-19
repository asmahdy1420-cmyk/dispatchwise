from __future__ import annotations

import pytest

from conftest import loc, make_order
from dispatchwise.errors import UnfulfillableOrderError
from dispatchwise.models import Pharmacy
from dispatchwise.splitting import (
    remaining_after,
    shortfall,
    single_source_pharmacies,
    split_order,
)


def test_single_source_sorted_by_distance(customer, pharmacies):
    order = make_order(customer, B=1)
    assert [p.id for p in single_source_pharmacies(order, pharmacies)] == ["near", "mid", "far"]


def test_greedy_prefers_fewest_pickups_over_proximity(customer, pharmacies):
    # "near" covers only A; "far" covers everything -> one pickup beats two closer ones.
    order = make_order(customer, A=2, C=2)
    pickups = split_order(order, pharmacies)
    assert [p.pharmacy_id for p in pickups] == ["far"]


def test_split_across_pharmacies_covers_every_unit(customer):
    pharmacies = [
        Pharmacy(id="p1", location=loc(25.29, 51.53), stock={"A": 3}),
        Pharmacy(id="p2", location=loc(25.30, 51.53), stock={"B": 2, "A": 1}),
        Pharmacy(id="p3", location=loc(25.31, 51.53), stock={"C": 5}),
    ]
    order = make_order(customer, A=4, B=2, C=1)
    pickups = split_order(order, pharmacies)

    assert len(pickups) == 3
    assert remaining_after(order, pickups) == {}
    totals: dict[str, int] = {}
    for p in pickups:
        for sku, qty in p.items.items():
            totals[sku] = totals.get(sku, 0) + qty
    assert totals == order.demand()


def test_tie_on_coverage_broken_by_distance(customer):
    pharmacies = [
        Pharmacy(id="far", location=loc(25.40, 51.53), stock={"A": 1}),
        Pharmacy(id="close", location=loc(25.29, 51.53), stock={"A": 1}),
    ]
    pickups = split_order(make_order(customer, A=1), pharmacies)
    assert pickups[0].pharmacy_id == "close"


def test_unfulfillable_reports_shortfall(customer, pharmacies):
    order = make_order(customer, A=50, Z=1)
    assert shortfall(order, pharmacies) == {"A": 35, "Z": 1}
    with pytest.raises(UnfulfillableOrderError) as info:
        split_order(order, pharmacies)
    assert info.value.shortfall == {"A": 35, "Z": 1}


def test_max_pickups_limit(customer):
    pharmacies = [
        Pharmacy(id=f"p{i}", location=loc(25.29 + i / 100, 51.53), stock={sku: 1})
        for i, sku in enumerate("ABC")
    ]
    order = make_order(customer, A=1, B=1, C=1)
    assert len(split_order(order, pharmacies, max_pickups=3)) == 3
    with pytest.raises(UnfulfillableOrderError):
        split_order(order, pharmacies, max_pickups=2)


def test_consolidation_keeps_each_sku_whole_when_possible(customer):
    # Greedy picks "mixed" first (covers 2 units), then "bulk" for the last AMOX.
    # Consolidation should move both AMOX boxes to "bulk" instead of 1 + 1.
    pharmacies = [
        Pharmacy(id="bulk", location=loc(25.32, 51.53), stock={"AMOX": 10}),
        Pharmacy(id="mixed", location=loc(25.29, 51.53), stock={"INS": 3, "AMOX": 1}),
    ]
    pickups = split_order(make_order(customer, AMOX=2, INS=1), pharmacies)
    by_id = {p.pharmacy_id: p.items for p in pickups}
    assert by_id == {"mixed": {"INS": 1}, "bulk": {"AMOX": 2}}
