"""Load and sanity-check the vehicle DBC.

The DBC is the single source of truth for IDs, signal layout, scaling and
message cycle times. Validation here catches DBC edits that would silently
break the rest of the stack (extended IDs, missing counter/checksum, ...).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import cantools
from cantools.database.can import Database

from app.can.frames import CHECKSUM_SIGNAL, COUNTER_SIGNAL, FRAME_LENGTH
from app.config import settings


class DbcValidationError(ValueError):
    """The DBC loaded but violates a project convention."""


def validate_database(db: Database) -> None:
    problems: list[str] = []
    for msg in db.messages:
        where = f"{msg.name} (0x{msg.frame_id:03X})"
        if msg.is_extended_frame or msg.frame_id > 0x7FF:
            problems.append(f"{where}: must use a standard 11-bit identifier")
        if msg.length != FRAME_LENGTH:
            problems.append(f"{where}: DLC must be {FRAME_LENGTH}, got {msg.length}")
        if not msg.cycle_time:
            problems.append(f"{where}: missing GenMsgCycleTime")
        if not msg.senders:
            problems.append(f"{where}: no sending node")

        names = {s.name: s for s in msg.signals}
        if COUNTER_SIGNAL not in names:
            problems.append(f"{where}: missing {COUNTER_SIGNAL} signal")
        checksum = names.get(CHECKSUM_SIGNAL)
        if checksum is None:
            problems.append(f"{where}: missing {CHECKSUM_SIGNAL} signal")
        elif (checksum.start, checksum.length) != (56, 8):
            problems.append(f"{where}: {CHECKSUM_SIGNAL} must occupy byte 7")

    if problems:
        raise DbcValidationError("Invalid DBC:\n  " + "\n  ".join(problems))


@lru_cache(maxsize=4)
def load_database(path: Path | None = None) -> Database:
    db = cantools.database.load_file(path or settings.dbc_path, strict=True)
    validate_database(db)
    return db
