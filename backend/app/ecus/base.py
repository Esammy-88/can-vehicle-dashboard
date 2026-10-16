"""Common ECU behaviour: receive, run control logic, transmit on schedule.

An ECU only knows the messages it sends (taken from the DBC by sender node)
and the frames it hears on its own bus. Transmission is scheduled on the
simulation clock, so cycle times are exact and tests are deterministic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

import can
from cantools.database.can import Message

from app.can.decoder import CanCodec
from app.can.frames import COUNTER_MODULO, DecodedFrame, SignalValue

# A received message is considered stale after this many missed cycles.
STALE_AFTER_CYCLES = 3
_TIME_EPSILON = 1e-6


@dataclass
class _TxSlot:
    message: Message
    period_s: float
    next_due: float = 0.0
    counter: int = 0


@dataclass(frozen=True)
class _RxEntry:
    received_at: float
    signals: dict[str, SignalValue]


class Ecu(ABC):
    node: ClassVar[str]

    def __init__(self, bus: can.BusABC, codec: CanCodec) -> None:
        self.bus = bus
        self.codec = codec
        self._tx = [
            _TxSlot(m, m.cycle_time / 1000.0) for m in codec.messages if self.node in m.senders
        ]
        self._rx_period = {m.name: m.cycle_time / 1000.0 for m in codec.messages}
        self._rx: dict[str, _RxEntry] = {}
        self.frames_sent = 0
        self.rx_errors = 0
        self.tx_enabled = True  # False while the bus is down: frames are lost on the wire
        self.suppressed: set[str] = set()  # messages this ECU has stopped sending (fault)

    def step(self, now: float) -> None:
        self._receive(now)
        self.update(now)
        self._transmit_due(now)

    @abstractmethod
    def update(self, now: float) -> None:
        """Run control logic for this tick."""

    @abstractmethod
    def signals_for(self, message_name: str) -> Mapping[str, SignalValue]:
        """Physical signal values for a message this ECU transmits."""

    def on_frame(self, frame: DecodedFrame, now: float) -> None:  # noqa: B027 - optional hook
        """Called for every received frame, valid or not. Override to observe traffic."""

    def reboot(self) -> None:
        """Power-cycle: drop queued traffic and anything learned from the bus."""
        while self.bus.recv(timeout=0) is not None:
            pass
        self._rx.clear()

    def latest(self, message_name: str, now: float) -> dict[str, SignalValue] | None:
        """Most recent signals of a received message, or None if missing/stale."""
        entry = self._rx.get(message_name)
        if entry is None:
            return None
        if now - entry.received_at > STALE_AFTER_CYCLES * self._rx_period[message_name]:
            return None
        return entry.signals

    def shutdown(self) -> None:
        self.bus.shutdown()

    def _receive(self, now: float) -> None:
        while (frame := self.bus.recv(timeout=0)) is not None:
            decoded = self.codec.decode(frame)
            self.on_frame(decoded, now)
            if decoded.ok:
                self._rx[decoded.name] = _RxEntry(now, decoded.signals)
            else:
                self.rx_errors += 1

    def _transmit_due(self, now: float) -> None:
        for slot in self._tx:
            if now + _TIME_EPSILON < slot.next_due:
                continue
            if slot.message.name not in self.suppressed:
                signals = _saturate(slot.message, self.signals_for(slot.message.name))
                frame = self.codec.encode(slot.message.name, signals, slot.counter)
                slot.counter = (slot.counter + 1) % COUNTER_MODULO
                if self.tx_enabled:
                    self.bus.send(frame)
                    self.frames_sent += 1
            slot.next_due += slot.period_s
            if slot.next_due + _TIME_EPSILON <= now:
                slot.next_due = now + slot.period_s  # fell behind: resync instead of bursting


def _saturate(message: Message, signals: Mapping[str, SignalValue]) -> dict[str, SignalValue]:
    """Clamp numeric values to the DBC range, as an ECU saturates a signal."""
    out = dict(signals)
    for sig in message.signals:
        value = out.get(sig.name)
        if isinstance(value, int | float) and not isinstance(value, bool):
            if sig.minimum is not None:
                value = max(sig.minimum, value)
            if sig.maximum is not None:
                value = min(sig.maximum, value)
            out[sig.name] = value
    return out
