"""FastAPI application entrypoint.

Run from the repository root:
    uvicorn app.main:app --app-dir backend --reload
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router
from app.config import settings

app = FastAPI(title=settings.app_name, version=settings.version)
app.include_router(router)
