"""Application configuration.

Settings come from environment variables so the same build can run on a
Linux host with SocketCAN (vcan0) or on Windows/macOS with the software bus.
Plain dataclass + os.environ keeps us free of an extra settings dependency.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class CanMode(StrEnum):
    # AUTO tries SocketCAN first and falls back to the in-process software bus.
    AUTO = "auto"
    SOCKETCAN = "socketcan"
    VIRTUAL = "virtual"


@dataclass(frozen=True)
class Settings:
    app_name: str = "CAN Vehicle Dashboard"
    version: str = "0.1.0"
    can_mode: CanMode = CanMode.AUTO
    can_channel: str = "vcan0"
    dbc_path: Path = field(default_factory=lambda: PROJECT_ROOT / "dbc" / "vehicle.dbc")
    log_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "logs")


def load_settings() -> Settings:
    return Settings(
        can_mode=CanMode(os.environ.get("CAN_MODE", CanMode.AUTO).lower()),
        can_channel=os.environ.get("CAN_CHANNEL", "vcan0"),
        log_dir=Path(os.environ.get("LOG_DIR", PROJECT_ROOT / "logs")),
    )


settings = load_settings()
