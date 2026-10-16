import time
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from apps.estimation.reeftrace_estimation.demo import make_demo

router = APIRouter()
_latest = None
_received = None


class Telemetry(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    type: Literal["telemetry"]
    uptime_ms: int = Field(ge=0)
    distance_cm: float | None = Field(default=None, ge=2, le=400)
    pot_raw: int = Field(ge=0, le=1023)
    armed: bool
    pan_deg: int = Field(ge=30, le=150)
    tilt_deg: int = Field(ge=60, le=120)


@router.post("/bench/telemetry")
def receive_telemetry(event: Telemetry):
    global _latest, _received
    _latest, _received = event.model_dump(), time.monotonic()
    return {"accepted": True}


@router.get("/bench")
def bench_status():
    age = None if _received is None else time.monotonic() - _received
    return {
        "connected": age is not None and age < 3,
        "age_seconds": age,
        "telemetry": _latest,
        "collection_enabled": False,
    }


@router.get("/demo/{scenario}")
def demo(scenario: Literal["moving", "stationary", "unknown"]):
    return make_demo(scenario)
