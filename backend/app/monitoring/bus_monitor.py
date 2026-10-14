"""Passive CAN bus monitor (the equivalent of a CAN analyser tap).

Listens on its own bus instance, never transmits. Every frame is decoded and
kept in a ring buffer for the CAN monitor page, and feeds the bus statistics:
rates per message and per ECU, errors, timeouts, active nodes and bus load.
All times are simulation time, so statistics are deterministic in tests.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any

import can

from app.can.decoder import CanCodec
from app.can.frames import DecodedFrame

BITRATE_BPS = 500_000  # classic high-speed CAN
RATE_WINDOW_S = 1.0
TIMEOUT_CYCLES = 3
UNKNOWN_SENDER = "UNKNOWN"


def frame_bits(dlc: int) -> int:
    """Bits on the wire for a standard-ID data frame, excluding bit stuffing.

    SOF 1 + ID 11 + RTR 1 + IDE 1 + r0 1 + DLC 4 + data 8*n + CRC 15 +
    CRC delimiter 1 + ACK 2 + EOF 7 + interframe space 3 = 47 + 8n.
    """
    return 47 + 8 * dlc


@dataclass
class _IdStats:
    name: str | None
    sender: str
    cycle_s: float | None
    count: int = 0
    errors: int = 0
    timeouts: int = 0
    last_seen: float | None = None
    timed_out: bool = False


@dataclass(frozen=True)
class _Seen:
    t: float
    arbitration_id: int
    sender: str
    bits: int


@dataclass
class BusMonitor:
    bus: can.BusABC
    codec: CanCodec
    buffer_size: int = 2000
    frames: deque[dict[str, Any]] = field(init=False)
    seq: int = 0
    total_frames: int = 0
    timeouts: int = 0
    errors_by_type: Counter[str] = field(default_factory=Counter)

    def __post_init__(self) -> None:
        self.frames = deque(maxlen=self.buffer_size)
        self._ids: dict[int, _IdStats] = {
            m.frame_id: _IdStats(m.name, m.senders[0], m.cycle_time / 1000.0)
            for m in self.codec.messages
        }
        self._window: deque[_Seen] = deque()

    def poll(self, now: float) -> None:
        while (frame := self.bus.recv(timeout=0)) is not None:
            self._record(self.codec.decode(frame), now)
        while self._window and self._window[0].t <= now - RATE_WINDOW_S:
            self._window.popleft()
        self._check_timeouts(now)

    def _record(self, d: DecodedFrame, now: float) -> None:
        self.seq += 1
        self.total_frames += 1
        sender = d.sender or UNKNOWN_SENDER
        stats = self._ids.get(d.arbitration_id)
        if stats is None:
            stats = self._ids[d.arbitration_id] = _IdStats(d.name, sender, None)
        stats.count += 1
        stats.last_seen = now
        stats.timed_out = False
        if d.error is not None:
            stats.errors += 1
            self.errors_by_type[d.error.value] += 1

        self._window.append(_Seen(now, d.arbitration_id, sender, frame_bits(d.dlc)))
        self.frames.append(
            {
                "seq": self.seq,
                "t": round(now, 3),
                "id": d.arbitration_id,
                "name": d.name,
                "sender": sender,
                "dlc": d.dlc,
                "data": d.data.hex(" ").upper(),
                "signals": d.signals,
                "error": d.error.value if d.error else None,
                "error_detail": d.error_detail,
            }
        )

    def _check_timeouts(self, now: float) -> None:
        for stats in self._ids.values():
            if stats.cycle_s is None or stats.last_seen is None or stats.timed_out:
                continue
            if now - stats.last_seen > TIMEOUT_CYCLES * stats.cycle_s:
                stats.timed_out = True
                stats.timeouts += 1
                self.timeouts += 1

    def frames_since(self, seq: int, limit: int = 500) -> list[dict[str, Any]]:
        new = [f for f in self.frames if f["seq"] > seq]
        return new[-limit:]

    def message_rate(self) -> float:
        return len(self._window) / RATE_WINDOW_S

    def stats(self, now: float) -> dict[str, Any]:
        window_ids = Counter(s.arbitration_id for s in self._window)
        window_ecus = Counter(s.sender for s in self._window)
        bits = sum(s.bits for s in self._window)
        return {
            "messages_per_s": self.message_rate(),
            "bus_load_pct": round(bits / RATE_WINDOW_S / BITRATE_BPS * 100.0, 2),
            "bitrate_bps": BITRATE_BPS,
            "total_frames": self.total_frames,
            "errors": sum(self.errors_by_type.values()),
            "errors_by_type": dict(self.errors_by_type),
            "timeouts": self.timeouts,
            "active_nodes": sorted(window_ecus),
            "per_ecu": [
                {"ecu": ecu, "rate": rate / RATE_WINDOW_S}
                for ecu, rate in sorted(window_ecus.items())
            ],
            "per_id": [
                {
                    "id": arb_id,
                    "name": s.name,
                    "sender": s.sender,
                    "cycle_ms": None if s.cycle_s is None else round(s.cycle_s * 1000),
                    "rate": window_ids.get(arb_id, 0) / RATE_WINDOW_S,
                    "count": s.count,
                    "errors": s.errors,
                    "timeouts": s.timeouts,
                    "timed_out": s.timed_out,
                    "last_seen_ago_s": None if s.last_seen is None else round(now - s.last_seen, 3),
                }
                for arb_id, s in sorted(self._ids.items())
            ],
        }
