"""Stateless FastAPI service around the planner."""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from dispatchwise import __version__
from dispatchwise.clustering import demand_zones, suggest_positioning
from dispatchwise.dispatcher import NoDriverAvailableError, UnfulfillableOrderError, plan_dispatch
from dispatchwise.models import CostWeights, DispatchPlan, Driver, Location, Order, Pharmacy
from dispatchwise.traffic import TrafficProfile


class PlanRequest(BaseModel):
    order: Order
    pharmacies: List[Pharmacy] = Field(min_length=1)
    drivers: List[Driver] = Field(min_length=1)
    hour: Optional[int] = Field(default=None, ge=0, le=23)
    weights: Optional[CostWeights] = None
    traffic: Optional[Dict[int, float]] = Field(
        default=None, description="Override multipliers for specific hours"
    )
    max_pickups: Optional[int] = Field(default=None, ge=1)
    max_alternatives: int = Field(default=3, ge=0, le=20)


class ZonesRequest(BaseModel):
    points: List[Location] = Field(min_length=1)
    k: int = Field(default=4, ge=1, le=50)
    drivers: List[Driver] = Field(default_factory=list)


app = FastAPI(
    title="dispatchwise",
    version=__version__,
    description="Multi-location pharmacy order dispatch optimiser.",
)


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.post("/v1/plan", response_model=DispatchPlan)
def plan(request: PlanRequest) -> DispatchPlan:
    try:
        traffic = TrafficProfile(request.traffic)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        return plan_dispatch(
            request.order,
            request.pharmacies,
            request.drivers,
            hour=request.hour,
            weights=request.weights,
            traffic=traffic,
            max_pickups=request.max_pickups,
            max_alternatives=request.max_alternatives,
        )
    except UnfulfillableOrderError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "unfulfillable", "message": str(exc), "shortfall": exc.shortfall},
        ) from exc
    except NoDriverAvailableError as exc:
        raise HTTPException(
            status_code=503, detail={"error": "no_driver_available", "message": str(exc)}
        ) from exc


@app.post("/v1/zones")
def zones(request: ZonesRequest) -> Dict[str, object]:
    try:
        found = demand_zones(request.points, k=request.k)
    except ImportError as exc:  # scikit-learn extra not installed
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    moves = suggest_positioning(found, request.drivers) if request.drivers else []
    return {
        "zones": [z.model_dump() for z in found],
        "positioning": [m.model_dump() for m in moves],
    }
