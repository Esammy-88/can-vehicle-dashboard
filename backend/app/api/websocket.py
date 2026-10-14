"""WebSocket streams for live dashboard data.

Both streams are incremental: each connection remembers the last history
sample / CAN frame it sent and only sends newer ones. If the simulation is
reset, the next message carries ``reset: true`` so the client clears its
buffers before applying the fresh data.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.simulation.runtime import SimulationRuntime

router = APIRouter()

TELEMETRY_INTERVAL_S = 0.05  # 20 Hz is smooth for gauges and light on the browser
CAN_INTERVAL_S = 0.1
CAN_INITIAL_FRAMES = 200


@router.websocket("/ws/telemetry")
async def telemetry(websocket: WebSocket) -> None:
    await websocket.accept()
    runtime: SimulationRuntime = websocket.app.state.runtime
    sim, last_seq = None, 0
    try:
        while True:
            reset = runtime.sim is not sim
            if reset:
                sim, last_seq = runtime.sim, 0
            samples = sim.history.since(last_seq)
            if samples:
                last_seq = samples[-1]["seq"]
            await websocket.send_json({**runtime.snapshot(), "samples": samples, "reset": reset})
            await asyncio.sleep(TELEMETRY_INTERVAL_S)
    except WebSocketDisconnect:
        pass  # client went away; nothing to clean up


@router.websocket("/ws/can")
async def can_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    runtime: SimulationRuntime = websocket.app.state.runtime
    sim, last_seq = None, 0
    try:
        while True:
            reset = runtime.sim is not sim
            if reset:
                sim = runtime.sim
                last_seq = max(0, sim.monitor.seq - CAN_INITIAL_FRAMES)
            frames = sim.monitor.frames_since(last_seq)
            if frames:
                last_seq = frames[-1]["seq"]
            await websocket.send_json(
                {"frames": frames, "stats": sim.monitor.stats(sim.time), "reset": reset}
            )
            await asyncio.sleep(CAN_INTERVAL_S)
    except WebSocketDisconnect:
        pass
