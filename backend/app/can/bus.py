"""CAN bus abstraction: SocketCAN when available, software bus otherwise.

Each simulated ECU opens its own bus instance, just as each physical ECU has
its own transceiver. On SocketCAN every instance is a socket on vcan0; on the
fallback, python-can's ``virtual`` interface delivers every frame to all other
instances on the same channel within this process.
"""

from __future__ import annotations

import logging
import sys
from enum import StrEnum

import can

from app.config import CanMode

log = logging.getLogger(__name__)


class CanBackend(StrEnum):
    SOCKETCAN = "socketcan"
    VIRTUAL = "virtual"


class CanInterfaceUnavailable(RuntimeError):
    """SocketCAN was explicitly requested but cannot be opened."""


def _probe_socketcan(channel: str) -> str | None:
    """Return None if SocketCAN ``channel`` can be opened, else the reason it can't."""
    if not sys.platform.startswith("linux"):
        return f"SocketCAN requires Linux (platform is {sys.platform})"
    try:
        bus = can.Bus(interface="socketcan", channel=channel)
    except (OSError, can.CanError) as exc:
        return f"cannot open {channel}: {exc}"
    bus.shutdown()
    return None


class BusFactory:
    """Resolves the CAN backend once, then opens one bus per node."""

    def __init__(self, mode: CanMode, channel: str) -> None:
        self.mode = mode
        self.channel = channel
        self.backend = self._resolve_backend()

    def _resolve_backend(self) -> CanBackend:
        if self.mode is CanMode.VIRTUAL:
            return CanBackend.VIRTUAL

        reason = _probe_socketcan(self.channel)
        if reason is None:
            return CanBackend.SOCKETCAN
        if self.mode is CanMode.SOCKETCAN:
            raise CanInterfaceUnavailable(reason)

        log.warning("SocketCAN unavailable (%s); using software CAN bus", reason)
        return CanBackend.VIRTUAL

    def open(self) -> can.BusABC:
        return can.Bus(
            interface=self.backend.value,
            channel=self.channel,
            receive_own_messages=False,
        )
