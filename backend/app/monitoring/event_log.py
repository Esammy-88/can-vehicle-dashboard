"""Event log: state changes, faults, warnings, recoveries, communication failures.

Events are kept in memory for the Logs page and appended to a JSON-lines file
(one JSON object per line) in the logs directory, so a run can be inspected
afterwards. Exports to JSON and CSV are generated from the in-memory buffer.
"""

from __future__ import annotations

import csv
import io
import json
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

Severity = Literal["INFO", "WARNING", "CRITICAL"]
MAX_EVENTS = 5000
CSV_FIELDS = ["seq", "timestamp", "sim_time", "severity", "event", "source", "message", "details"]


@dataclass(frozen=True)
class Event:
    seq: int
    timestamp: str  # wall clock, ISO 8601 UTC
    sim_time: float
    severity: Severity
    event: str
    source: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventLog:
    def __init__(self, log_dir: Path | None = None) -> None:
        self._events: deque[Event] = deque(maxlen=MAX_EVENTS)
        self.seq = 0
        self.path: Path | None = None
        if log_dir is not None:
            log_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            self.path = log_dir / f"events-{stamp}.jsonl"

    def add(
        self,
        event: str,
        severity: Severity,
        source: str,
        message: str,
        sim_time: float,
        **details: Any,
    ) -> Event:
        self.seq += 1
        entry = Event(
            seq=self.seq,
            timestamp=datetime.now(UTC).isoformat(timespec="milliseconds"),
            sim_time=round(sim_time, 3),
            severity=severity,
            event=event,
            source=source,
            message=message,
            details=details,
        )
        self._events.append(entry)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
        return entry

    def since(self, seq: int, limit: int = 500) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self._events if e.seq > seq][-limit:]

    def recent(self, limit: int = 500) -> list[dict[str, Any]]:
        return [e.to_dict() for e in list(self._events)[-limit:]]

    def to_json(self) -> str:
        return json.dumps([e.to_dict() for e in self._events], indent=2)

    def to_csv(self) -> str:
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for e in self._events:
            row = e.to_dict()
            row["details"] = json.dumps(row["details"]) if row["details"] else ""
            writer.writerow(row)
        return out.getvalue()
