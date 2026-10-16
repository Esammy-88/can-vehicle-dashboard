"""Diagnostic monitor node (DIAG): ECU health and trouble codes.

Listens to the whole bus. A watchdog tracks every ECU's liveness; DTCs are
collected from what the ECUs broadcast (ENGINE_TEMPERATURE, TRANSMISSION_
STATUS) plus network codes this node raises itself: U01xx when an ECU goes
silent, U0001 when the whole bus is quiet, U0401 when the ECM's frames arrive
corrupted. DIAGNOSTIC_STATUS summarises it all once a second.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import can

from app.can.decoder import CanCodec
from app.can.frames import COUNTER_SIGNAL, DecodedFrame, SignalValue
from app.ecus import dtc
from app.ecus.base import Ecu
from app.monitoring.watchdog import Watchdog, WatchdogEvent

WATCHED = {
    "ECM": "Engine ECU",
    "TCM": "Transmission ECU",
    "BCM": "Body ECU",
    "IPC": "Dashboard ECU",
}
LOST_COMM_DTC = {"ECM": "U0100", "TCM": "U0101", "BCM": "U0140", "IPC": "U0155"}
ONLINE_SIGNALS = {"ECM": "EcmOnline", "TCM": "TcmOnline", "BCM": "BcmOnline", "IPC": "IpcOnline"}
STARTUP_GRACE_S = 1.5
INVALID_WINDOW_S = 1.0
INVALID_THRESHOLD = 3  # corrupted ECM frames per window before U0401 is set
DTC_HISTORY = 200


@dataclass
class DtcRecord:
    code: str
    ecu: str
    set_at: float
    cleared_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "ecu": self.ecu,
            "description": dtc.describe(self.code),
            "set_at": round(self.set_at, 2),
            "cleared_at": None if self.cleared_at is None else round(self.cleared_at, 2),
        }


@dataclass
class DtcEvent:
    event: str  # DTC_SET or DTC_CLEARED
    record: DtcRecord


@dataclass
class _EcuCodes:
    """Codes one ECU is currently reporting (it rotates through them)."""

    seen: dict[str, float] = field(default_factory=dict)
    count: int = 0


class DiagnosticEcu(Ecu):
    node = "DIAG"

    def __init__(self, bus: can.BusABC, codec: CanCodec) -> None:
        super().__init__(bus, codec)
        self.watchdog = Watchdog(WATCHED)
        self.active: dict[tuple[str, str], DtcRecord] = {}
        self.history: deque[DtcRecord] = deque(maxlen=DTC_HISTORY)
        self.events: list[WatchdogEvent | DtcEvent] = []  # drained by the simulator
        self.last_frame_at: float | None = None
        self._reported: dict[str, _EcuCodes] = {"ECM": _EcuCodes(), "TCM": _EcuCodes()}
        self._invalid_ecm: deque[float] = deque()

    def on_frame(self, frame: DecodedFrame, now: float) -> None:
        self.last_frame_at = now
        if not frame.ok:
            if frame.sender == "ECM":
                self._invalid_ecm.append(now)
            return
        counter = frame.signals.get(COUNTER_SIGNAL)
        event = self.watchdog.feed(frame.sender, frame.name, int(counter), now)
        if event:
            self.events.append(event)
        if frame.name == "ENGINE_TEMPERATURE":
            self._note_codes(
                "ECM", frame.signals["EngineDtc"], frame.signals["EngineDtcCount"], now
            )
        elif frame.name == "TRANSMISSION_STATUS":
            code = frame.signals["TransDtc"]
            self._note_codes("TCM", code, 1 if code else 0, now)

    def _note_codes(self, ecu: str, code: SignalValue, count: SignalValue, now: float) -> None:
        reported = self._reported[ecu]
        reported.count = int(count)
        if reported.count == 0:
            reported.seen.clear()
        elif code:
            reported.seen[dtc.decode(int(code))] = now

    def update(self, now: float) -> None:
        self.events.extend(self.watchdog.check(now))
        while self._invalid_ecm and self._invalid_ecm[0] <= now - INVALID_WINDOW_S:
            self._invalid_ecm.popleft()
        self._sync_dtcs(self._wanted_dtcs(now), now)

    def _wanted_dtcs(self, now: float) -> set[tuple[str, str]]:
        wanted: set[tuple[str, str]] = set()
        for ecu, reported in self._reported.items():
            # A code the ECU has stopped rotating through is no longer active.
            stale_after = max(2.0, reported.count * 1.5)
            for code, seen_at in reported.seen.items():
                if now - seen_at <= stale_after and self.watchdog.ecus[ecu].online:
                    wanted.add((ecu, code))
        if now > STARTUP_GRACE_S:
            silent = [n for n, w in self.watchdog.ecus.items() if not w.online]
            if len(silent) == len(WATCHED):
                wanted.add(("DIAG", "U0001"))
            else:
                wanted.update(("DIAG", LOST_COMM_DTC[n]) for n in silent)
        if len(self._invalid_ecm) >= INVALID_THRESHOLD:
            wanted.add(("DIAG", "U0401"))
        elif ("DIAG", "U0401") in self.active and self._invalid_ecm:
            wanted.add(("DIAG", "U0401"))  # hold until the corruption has stopped
        return wanted

    def _sync_dtcs(self, wanted: set[tuple[str, str]], now: float) -> None:
        for key in wanted - self.active.keys():
            ecu, code = key
            record = DtcRecord(code, ecu, now)
            self.active[key] = record
            self.history.append(record)
            self.events.append(DtcEvent("DTC_SET", record))
        for key in self.active.keys() - wanted:
            record = self.active.pop(key)
            record.cleared_at = now
            self.events.append(DtcEvent("DTC_CLEARED", record))

    def clear_history(self) -> None:
        """Like a scan tool's 'clear codes': forget cleared codes, keep active ones."""
        self.history = deque((r for r in self.history if r.cleared_at is None), maxlen=DTC_HISTORY)

    def signals_for(self, message_name: str) -> Mapping[str, SignalValue]:
        latest = max(self.active.values(), key=lambda r: r.set_at, default=None)
        return {
            **{sig: int(self.watchdog.ecus[n].online) for n, sig in ONLINE_SIGNALS.items()},
            "ActiveDtcCount": len(self.active),
            "LastDtc": dtc.encode(latest.code) if latest else 0,
        }

    def view(self, now: float) -> dict[str, Any]:
        return {
            "ecus": [
                {
                    "node": w.node,
                    "name": w.name,
                    "online": w.online,
                    "last_message": w.last_message,
                    "last_seen_ago_s": None if w.last_seen is None else round(now - w.last_seen, 3),
                    "timeouts": w.timeouts,
                    "counter_errors": w.counter_errors,
                }
                for w in self.watchdog.ecus.values()
            ],
            "last_frame_ago_s": None
            if self.last_frame_at is None
            else round(now - self.last_frame_at, 3),
            "active_dtcs": [
                r.to_dict() for r in sorted(self.active.values(), key=lambda r: r.set_at)
            ],
            "dtc_history": [r.to_dict() for r in reversed(self.history)],
        }
