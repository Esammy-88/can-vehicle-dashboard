"""REST endpoints for configuration and control operations.

Handlers are ``async`` on purpose: they then run on the event loop thread,
the same thread that steps the simulation, so no locking is needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.monitoring.can_trace import CanTraceRecorder
from app.simulation.faults import CATALOG, FaultError, FaultType
from app.simulation.runtime import SimulationRuntime
from app.simulation.vehicle import Headlights, Selector, TurnIndicator

router = APIRouter(prefix="/api")

LOG_SUFFIXES = {".jsonl", ".log"}


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


# --- Fault injection ---------------------------------------------------------


class FaultRequest(BaseModel):
    type: FaultType
    target: str | None = None


@router.get("/faults")
async def list_faults(runtime: Runtime) -> dict[str, Any]:
    return {
        "catalog": [
            {
                "type": kind.value,
                "label": spec.label,
                "description": spec.description,
                "targets": list(spec.targets),
            }
            for kind, spec in CATALOG.items()
        ],
        "active": runtime.sim.faults.to_list(),
    }


@router.post("/faults")
async def inject_fault(request: FaultRequest, runtime: Runtime) -> list[dict[str, Any]]:
    try:
        runtime.sim.faults.inject(request.type, request.target)
    except FaultError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return runtime.sim.faults.to_list()


@router.delete("/faults/{fault_type}")
async def clear_fault(
    fault_type: FaultType, runtime: Runtime, target: str | None = None
) -> list[dict[str, Any]]:
    if not runtime.sim.faults.clear(fault_type, target):
        raise HTTPException(status_code=404, detail="Fault is not active")
    return runtime.sim.faults.to_list()


@router.delete("/faults")
async def clear_all_faults(runtime: Runtime) -> list[dict[str, Any]]:
    runtime.sim.faults.clear_all()
    return runtime.sim.faults.to_list()


# --- Diagnostics -------------------------------------------------------------


@router.get("/diagnostics")
async def diagnostics(runtime: Runtime) -> dict[str, Any]:
    return runtime.sim.diagnostics.view(runtime.sim.time)


@router.delete("/diagnostics/dtcs")
async def clear_dtc_history(runtime: Runtime) -> dict[str, Any]:
    runtime.sim.diagnostics.clear_history()
    runtime.events.add(
        "DTC_HISTORY_CLEARED", "INFO", "DIAG", "DTC history cleared", runtime.sim.time
    )
    return runtime.sim.diagnostics.view(runtime.sim.time)


# --- Event log and CAN traces --------------------------------------------------


@router.get("/logs")
async def logs(
    runtime: Runtime, limit: Annotated[int, Query(ge=1, le=5000)] = 500
) -> list[dict[str, Any]]:
    return runtime.events.recent(limit)


@router.get("/logs/export")
async def export_logs(runtime: Runtime, format: Literal["json", "csv"] = "json") -> Response:
    body, media = (
        (runtime.events.to_csv(), "text/csv")
        if format == "csv"
        else (runtime.events.to_json(), "application/json")
    )
    return Response(
        body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="events.{format}"'},
    )


class TraceRequest(BaseModel):
    action: Literal["start", "stop"]


def _require_trace(runtime: SimulationRuntime) -> CanTraceRecorder:
    if runtime.trace is None:
        raise HTTPException(status_code=503, detail="No log directory configured")
    return runtime.trace


@router.get("/logs/trace")
async def trace_status(runtime: Runtime) -> dict[str, Any]:
    return _require_trace(runtime).status()


@router.post("/logs/trace")
async def trace_control(request: TraceRequest, runtime: Runtime) -> dict[str, Any]:
    trace = _require_trace(runtime)
    if request.action == "start" and not trace.recording:
        path = trace.start()
        runtime.events.add(
            "TRACE_STARTED",
            "INFO",
            "SYSTEM",
            f"CAN trace recording to {path.name}",
            runtime.sim.time,
        )
    elif request.action == "stop" and trace.recording:
        trace.stop()
        runtime.events.add(
            "TRACE_STOPPED",
            "INFO",
            "SYSTEM",
            f"CAN trace stopped ({trace.frames} frames)",
            runtime.sim.time,
        )
    return trace.status()


@router.get("/logs/files")
async def log_files(runtime: Runtime) -> list[dict[str, Any]]:
    if runtime.log_dir is None or not runtime.log_dir.exists():
        return []
    files = sorted(
        (p for p in runtime.log_dir.iterdir() if p.suffix in LOG_SUFFIXES and p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return [{"name": p.name, "bytes": p.stat().st_size} for p in files]


@router.get("/logs/files/{name}")
async def download_log_file(name: str, runtime: Runtime) -> FileResponse:
    # Only plain file names from the log directory: no paths, no traversal.
    if runtime.log_dir is None or Path(name).name != name or Path(name).suffix not in LOG_SUFFIXES:
        raise HTTPException(status_code=404, detail="Not found")
    path = runtime.log_dir / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, filename=name)
