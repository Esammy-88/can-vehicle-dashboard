"""DBC-driven encoding and decoding of CAN frames.

Encoding is strict: unknown messages, missing signals and out-of-range values
raise, because they are bugs in the sending ECU. Decoding never raises: a bad
frame on the bus is data to report (CAN monitor, diagnostics), not a crash.
"""

from __future__ import annotations

from collections.abc import Mapping

import can
from cantools.database.can import Database, Message
from cantools.database.errors import Error as CantoolsError
from cantools.database.namedsignalvalue import NamedSignalValue

from app.can.frames import (
    CHECKSUM_BYTE,
    CHECKSUM_SIGNAL,
    COUNTER_MODULO,
    COUNTER_SIGNAL,
    DecodedFrame,
    FrameError,
    SignalValue,
    compute_checksum,
)


class CanEncodeError(ValueError):
    """An ECU tried to transmit an invalid message."""


class CanCodec:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._by_id: dict[int, Message] = {m.frame_id: m for m in db.messages}

    @property
    def messages(self) -> list[Message]:
        return list(self._db.messages)

    def message(self, name: str) -> Message:
        try:
            return self._db.get_message_by_name(name)
        except KeyError:
            raise CanEncodeError(f"Unknown message {name!r}") from None

    def encode(
        self, name: str, signals: Mapping[str, SignalValue], counter: int = 0
    ) -> can.Message:
        """Build a frame; the alive counter and checksum are filled in here."""
        msg = self.message(name)
        values = {
            **signals,
            COUNTER_SIGNAL: counter % COUNTER_MODULO,
            CHECKSUM_SIGNAL: 0,
        }
        try:
            data = bytearray(msg.encode(values, strict=True))
        except CantoolsError as exc:
            raise CanEncodeError(f"{name}: {exc}") from exc

        data[CHECKSUM_BYTE] = compute_checksum(msg.frame_id, data)
        return can.Message(arbitration_id=msg.frame_id, data=data, is_extended_id=False)

    def decode(self, frame: can.Message) -> DecodedFrame:
        base = {
            "timestamp": frame.timestamp,
            "arbitration_id": frame.arbitration_id,
            "dlc": frame.dlc,
            "data": bytes(frame.data),
        }
        if frame.is_error_frame:
            return DecodedFrame(**base, error=FrameError.ERROR_FRAME)

        msg = None if frame.is_extended_id else self._by_id.get(frame.arbitration_id)
        if msg is None:
            return DecodedFrame(**base, error=FrameError.UNKNOWN_ID)

        known = {"name": msg.name, "sender": msg.senders[0]}
        if frame.dlc != msg.length or len(frame.data) != msg.length:
            return DecodedFrame(
                **base,
                **known,
                error=FrameError.BAD_DLC,
                error_detail=f"expected {msg.length} bytes, got {len(frame.data)}",
            )

        try:
            raw = msg.decode(frame.data, decode_choices=True, scaling=True)
        except CantoolsError as exc:
            return DecodedFrame(**base, **known, error=FrameError.MALFORMED, error_detail=str(exc))
        signals = {k: str(v) if isinstance(v, NamedSignalValue) else v for k, v in raw.items()}

        expected = compute_checksum(msg.frame_id, frame.data)
        if frame.data[CHECKSUM_BYTE] != expected:
            return DecodedFrame(
                **base,
                **known,
                signals=signals,
                error=FrameError.CHECKSUM,
                error_detail=f"expected 0x{expected:02X}, got 0x{frame.data[CHECKSUM_BYTE]:02X}",
            )

        return DecodedFrame(**base, **known, signals=signals)
