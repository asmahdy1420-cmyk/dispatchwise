from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dispatchwise.api import app

client = TestClient(app)

PHARMACIES = [
    {"id": "p1", "location": {"lat": 25.29, "lon": 51.53}, "stock": {"A": 2}, "queue_length": 1},
    {"id": "p2", "location": {"lat": 25.30, "lon": 51.54}, "stock": {"B": 2}},
]
DRIVERS = [{"id": "d1", "location": {"lat": 25.28, "lon": 51.52}, "current_load": 1}]
ORDER = {
    "id": "o-42",
    "customer": {"lat": 25.2854, "lon": 51.5310},
    "lines": [{"sku": "A", "quantity": 1}, {"sku": "B", "quantity": 1}],
}


def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_plan_endpoint_returns_split_plan():
    response = client.post(
        "/v1/plan",
        json={"order": ORDER, "pharmacies": PHARMACIES, "drivers": DRIVERS, "hour": 8},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["split"] is True
    assert body["driver_id"] == "d1"
    assert body["route"][-1] == "customer"
    assert body["cost"]["traffic_multiplier"] == 1.6


def test_plan_endpoint_409_on_shortfall():
    order = {**ORDER, "lines": [{"sku": "A", "quantity": 9}]}
    response = client.post(
        "/v1/plan", json={"order": order, "pharmacies": PHARMACIES, "drivers": DRIVERS}
    )
    assert response.status_code == 409
    assert response.json()["detail"]["shortfall"] == {"A": 7}


def test_plan_endpoint_validates_input():
    order = {**ORDER, "lines": []}
    response = client.post(
        "/v1/plan", json={"order": order, "pharmacies": PHARMACIES, "drivers": DRIVERS}
    )
    assert response.status_code == 422


def test_zones_endpoint():
    pytest.importorskip("sklearn")
    points = [{"lat": 25.30, "lon": 51.40}] * 5 + [{"lat": 25.30, "lon": 51.60}] * 5
    response = client.post("/v1/zones", json={"points": points, "k": 2})
    assert response.status_code == 200
    assert len(response.json()["zones"]) == 2
