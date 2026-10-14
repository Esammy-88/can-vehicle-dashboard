"""WebSocket streams for live dashboard data."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

TELEMETRY_INTERVAL_S = 0.05  # 20 Hz is smooth for gauges and light on the browser


@router.websocket("/ws/telemetry")
async def telemetry(websocket: WebSocket) -> None:
    await websocket.accept()
    runtime = websocket.app.state.runtime
    try:
        while True:
            await websocket.send_json(runtime.snapshot())
            await asyncio.sleep(TELEMETRY_INTERVAL_S)
    except WebSocketDisconnect:
        pass  # client went away; nothing to clean up
