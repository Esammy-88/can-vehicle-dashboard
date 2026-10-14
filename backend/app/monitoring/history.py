"""Rolling telemetry history for the real-time graphs.

Samples the instrument cluster's CAN-decoded view at a fixed simulation-time
interval and keeps the last few minutes, so the graphs can show any range up
to MAX_AGE_S and a reloaded page gets the history back immediately.
"""

from __future__ import annotations

from collections import deque
from typing import Any

SAMPLE_INTERVAL_S = 0.2
MAX_AGE_S = 300.0

# History field -> cluster view key
FIELDS = {
    "speed_kmh": "speed_kmh",
    "rpm": "rpm",
    "coolant_c": "coolant_c",
    "oil_c": "oil_c",
    "fuel_pct": "fuel_pct",
    "engine_load": "engine_load",
}


class TelemetryHistory:
    def __init__(self) -> None:
        self._samples: deque[dict[str, Any]] = deque(maxlen=round(MAX_AGE_S / SAMPLE_INTERVAL_S))
        self._next_at = 0.0
        self.seq = 0

    def due(self, now: float) -> bool:
        return now + 1e-9 >= self._next_at

    def sample(self, now: float, view: dict[str, Any], can_rate: float) -> None:
        self.seq += 1
        self._next_at = now + SAMPLE_INTERVAL_S
        point: dict[str, Any] = {"seq": self.seq, "t": round(now, 2), "can_rate": can_rate}
        for key, view_key in FIELDS.items():
            point[key] = view[view_key]
        self._samples.append(point)

    def since(self, seq: int) -> list[dict[str, Any]]:
        return [s for s in self._samples if s["seq"] > seq]

    def window(self, seconds: float) -> list[dict[str, Any]]:
        if not self._samples:
            return []
        start = self._samples[-1]["t"] - seconds
        return [s for s in self._samples if s["t"] >= start]
