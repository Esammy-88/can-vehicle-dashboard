"""Raw CAN trace recording in candump log format.

Lines look like ``(1792010225.953377) vcan0 100#80C0201B05000032``, the format
of Linux can-utils' ``candump -l``. Traces can be replayed with ``canplayer``
on a vcan interface and inspected in Wireshark from there, or read back with
python-can's ``can.LogReader``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import can


class CanTraceRecorder:
    def __init__(self, log_dir: Path, channel: str) -> None:
        self._log_dir = log_dir
        self._channel = channel
        self._writer: can.CanutilsLogWriter | None = None
        self.path: Path | None = None
        self.frames = 0

    @property
    def recording(self) -> bool:
        return self._writer is not None

    def start(self) -> Path:
        if self._writer is None:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            self.path = self._log_dir / f"can-trace-{stamp}.log"
            self._writer = can.CanutilsLogWriter(self.path, channel=self._channel)
            self.frames = 0
        assert self.path is not None
        return self.path

    def stop(self) -> None:
        if self._writer is not None:
            self._writer.stop()
            self._writer = None

    def record(self, frame: can.Message) -> None:
        if self._writer is not None:
            self._writer.on_message_received(frame)
            self.frames += 1

    def status(self) -> dict[str, object]:
        return {
            "recording": self.recording,
            "file": self.path.name if self.path else None,
            "frames": self.frames,
        }
