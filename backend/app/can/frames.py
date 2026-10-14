"""Frame-level conventions shared by every message on the network.

Every message reserves byte 6 (low nibble) for a rolling alive counter and
byte 7 for a checksum, the same end-to-end protection pattern production ECUs
use to detect stale, repeated or corrupted frames.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

FRAME_LENGTH = 8
COUNTER_SIGNAL = "AliveCounter"
CHECKSUM_SIGNAL = "Checksum"
CHECKSUM_BYTE = 7
COUNTER_MODULO = 16

SignalValue = int | float | str


class FrameError(StrEnum):
    UNKNOWN_ID = "UNKNOWN_ID"
    BAD_DLC = "BAD_DLC"
    CHECKSUM = "CHECKSUM"
    MALFORMED = "MALFORMED"
    ERROR_FRAME = "ERROR_FRAME"


def compute_checksum(arbitration_id: int, data: bytes | bytearray) -> int:
    """Checksum over payload bytes 0-6 and the CAN ID.

    Mixing in the ID means a valid payload replayed under the wrong ID fails.
    """
    total = sum(data[:CHECKSUM_BYTE]) + (arbitration_id & 0xFF) + (arbitration_id >> 8)
    return (total & 0xFF) ^ 0xFF


@dataclass(frozen=True)
class DecodedFrame:
    timestamp: float
    arbitration_id: int
    dlc: int
    data: bytes
    name: str | None = None
    sender: str | None = None
    signals: dict[str, SignalValue] = field(default_factory=dict)
    error: FrameError | None = None
    error_detail: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None
