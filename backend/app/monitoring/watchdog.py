"""Software watchdog for ECU liveness.

Every ECU proves it is alive by transmitting its periodic messages, each with
a rolling alive counter. The watchdog declares an ECU OFFLINE when nothing
has been heard from it for ``timeout_s`` and ONLINE again on its next frame.
It also checks the alive counters: a repeated value means the sender is
stuck re-sending stale data, a jump means frames were lost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.can.frames import COUNTER_MODULO

ECU_TIMEOUT_S = 1.5  # spec: heartbeat every 500 ms, offline after 1500 ms


@dataclass
class EcuWatch:
    node: str
    name: str
    online: bool = False
    last_seen: float | None = None
    last_message: str | None = None
    timeouts: int = 0
    counter_errors: int = 0
    _counters: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class WatchdogEvent:
    event: str  # ECU_TIMEOUT or ECU_ONLINE
    node: str
    name: str
    time: float
    last_message: str | None
    last_seen: float | None
    timeout_s: float

    def details(self) -> dict[str, Any]:
        return {
            "ecu": self.node,
            "last_message": self.last_message,
            "last_seen_s": None if self.last_seen is None else round(self.last_seen, 3),
            "timeout_s": self.timeout_s,
        }


class Watchdog:
    def __init__(self, nodes: dict[str, str], timeout_s: float = ECU_TIMEOUT_S) -> None:
        self.timeout_s = timeout_s
        self.ecus = {node: EcuWatch(node, name) for node, name in nodes.items()}

    def feed(
        self, node: str, message: str, counter: int | None, now: float
    ) -> WatchdogEvent | None:
        watch = self.ecus.get(node)
        if watch is None:
            return None
        if counter is not None:
            previous = watch._counters.get(message)
            if previous is not None and (counter - previous) % COUNTER_MODULO != 1:
                watch.counter_errors += 1
            watch._counters[message] = counter
        watch.last_seen, watch.last_message = now, message
        if watch.online:
            return None
        watch.online = True
        return WatchdogEvent("ECU_ONLINE", node, watch.name, now, message, now, self.timeout_s)

    def check(self, now: float) -> list[WatchdogEvent]:
        events = []
        for watch in self.ecus.values():
            silent_since = watch.last_seen if watch.last_seen is not None else 0.0
            if watch.online and now - silent_since > self.timeout_s:
                watch.online = False
                watch.timeouts += 1
                events.append(
                    WatchdogEvent(
                        "ECU_TIMEOUT",
                        watch.node,
                        watch.name,
                        now,
                        watch.last_message,
                        watch.last_seen,
                        self.timeout_s,
                    )
                )
        return events
