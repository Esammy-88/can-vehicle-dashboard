"""REST endpoints for configuration and control operations."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/api")


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    can_mode: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.version,
        can_mode=settings.can_mode.value,
    )
