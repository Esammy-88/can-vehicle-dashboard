"""FastAPI application entrypoint.

Run from the repository root:
    uvicorn app.main:app --app-dir backend --reload --reload-dir backend
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.api.websocket import router as ws_router
from app.can.bus import BusFactory
from app.can.dbc_loader import load_database
from app.can.decoder import CanCodec
from app.config import settings
from app.simulation.runtime import SimulationRuntime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    codec = CanCodec(load_database())
    factory = BusFactory(settings.can_mode, settings.can_channel)
    runtime = SimulationRuntime(factory, codec, log_dir=settings.log_dir)
    runtime.start()
    app.state.runtime = runtime
    logging.getLogger(__name__).info(
        "Simulation running on %s CAN bus (%s)", factory.backend, factory.channel
    )
    yield
    await runtime.stop()


app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)
app.include_router(router)
app.include_router(ws_router)
