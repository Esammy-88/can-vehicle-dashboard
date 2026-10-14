"""REST endpoints for configuration and control operations.

Handlers are ``async`` on purpose: they then run on the event loop thread,
the same thread that steps the simulation, so no locking is needed.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.simulation.runtime import SimulationRuntime
from app.simulation.vehicle import Headlights, Selector, TurnIndicator

router = APIRouter(prefix="/api")


def get_runtime(request: Request) -> SimulationRuntime:
    return request.app.state.runtime


Runtime = Annotated[SimulationRuntime, Depends(get_runtime)]


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    can_mode: str
    can_backend: str


@router.get("/health", response_model=HealthResponse)
async def health(runtime: Runtime) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.version,
        can_mode=settings.can_mode.value,
        can_backend=runtime.factory.backend.value,
    )


@router.get("/state")
async def state(runtime: Runtime) -> dict[str, Any]:
    return runtime.snapshot()


DoorName = Literal["front_left", "front_right", "rear_left", "rear_right"]


class ControlsUpdate(BaseModel):
    """Partial update of the driver's controls; omitted fields are unchanged."""

    ignition: bool | None = None
    throttle: float | None = Field(None, ge=0, le=100)
    brake: float | None = Field(None, ge=0, le=100)
    gear_selector: Selector | None = None
    headlights: Headlights | None = None
    turn_indicator: TurnIndicator | None = None
    doors_open: dict[DoorName, bool] | None = None
    seatbelt_fastened: bool | None = None


@router.post("/controls")
async def update_controls(update: ControlsUpdate, runtime: Runtime) -> dict[str, Any]:
    driver = runtime.sim.driver
    changes = update.model_dump(exclude_none=True)
    driver.doors_open.update(changes.pop("doors_open", {}))
    for key, value in changes.items():
        setattr(driver, key, value)
    return runtime.snapshot()["controls"]


class SpeedUpdate(BaseModel):
    factor: Literal[0.5, 1, 2, 5]


@router.post("/simulation/{action}")
async def simulation_action(
    action: Literal["start", "pause", "reset"],
    runtime: Runtime,
) -> dict[str, Any]:
    {"start": runtime.resume, "pause": runtime.pause, "reset": runtime.reset}[action]()
    return runtime.status()


@router.put("/simulation/speed")
async def simulation_speed(update: SpeedUpdate, runtime: Runtime) -> dict[str, Any]:
    runtime.set_speed(float(update.factor))
    return runtime.status()


@router.get("/can/stats")
async def can_stats(runtime: Runtime) -> dict[str, Any]:
    return runtime.sim.monitor.stats(runtime.sim.time)


@router.get("/can/frames")
async def can_frames(
    runtime: Runtime, limit: Annotated[int, Query(ge=1, le=2000)] = 200
) -> list[dict[str, Any]]:
    return list(runtime.sim.monitor.frames)[-limit:]


@router.get("/history")
async def history(
    runtime: Runtime, seconds: Annotated[float, Query(gt=0, le=300)] = 60
) -> list[dict[str, Any]]:
    return runtime.sim.history.window(seconds)
