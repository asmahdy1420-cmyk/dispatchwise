from __future__ import annotations

import contextlib

import pytest

from conftest import loc
from dispatchwise.cli import main
from dispatchwise.dispatcher import DispatchError, plan_dispatch
from dispatchwise.models import Driver
from dispatchwise.synthetic import generate_scenario


def test_generator_is_reproducible_and_produces_split_orders():
    a = generate_scenario(n_orders=60, seed=7)
    b = generate_scenario(n_orders=60, seed=7)
    assert a.model_dump() == b.model_dump()
    assert len(a.pharmacies) == 8 and len(a.orders) == 60

    plans = []
    for order in a.orders:
        with contextlib.suppress(DispatchError):
            plans.append(plan_dispatch(order, a.pharmacies, a.drivers, hour=12))
    assert plans, "at least some orders should be plannable"
    assert any(p.split for p in plans), "sparse stock should force some splits"


def test_cli_generate_and_plan(tmp_path, capsys):
    path = tmp_path / "scenario.json"
    assert main(["generate", "-o", str(path), "--orders", "20", "--seed", "3"]) == 0
    assert main(["plan", str(path), "--count", "5", "--hour", "9"]) == 0
    out = capsys.readouterr().out
    assert "5 orders" in out


def test_demand_zones_find_obvious_clusters():
    pytest.importorskip("sklearn")
    from dispatchwise.clustering import demand_zones

    west = [loc(25.30 + i * 1e-4, 51.40) for i in range(30)]
    east = [loc(25.30 + i * 1e-4, 51.60) for i in range(10)]
    zones = demand_zones(west + east, k=2)

    assert [z.order_count for z in zones] == [30, 10]
    assert zones[0].centre.lon == pytest.approx(51.40, abs=1e-3)
    assert zones[1].centre.lon == pytest.approx(51.60, abs=1e-3)
    assert sum(z.share for z in zones) == pytest.approx(1.0)


def test_positioning_allocates_idle_drivers_by_demand():
    pytest.importorskip("sklearn")
    from dispatchwise.clustering import allocate_drivers, demand_zones, suggest_positioning

    points = [loc(25.30, 51.40)] * 30 + [loc(25.30, 51.60)] * 10
    zones = demand_zones(points, k=2)
    assert allocate_drivers(zones, 4) == {zones[0].zone_id: 3, zones[1].zone_id: 1}

    drivers = [
        Driver(id=f"d{i}", location=loc(25.30, 51.40 + i * 0.05), current_load=0) for i in range(4)
    ] + [Driver(id="busy", location=loc(25.30, 51.50), current_load=2)]
    moves = suggest_positioning(zones, drivers)

    assert len(moves) == 4
    assert "busy" not in {m.driver_id for m in moves}
    east = [m for m in moves if m.zone_id == zones[1].zone_id]
    assert [m.driver_id for m in east] == ["d3"]
