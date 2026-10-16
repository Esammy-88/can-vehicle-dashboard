from pathlib import Path

import pytest

from app.can.dbc_loader import DbcValidationError, load_database

# (frame id, name, sender, cycle time ms) — spec sections 5 and 6.
EXPECTED_MESSAGES = [
    (0x100, "ENGINE_STATUS", "ECM", 100),
    (0x101, "ENGINE_TEMPERATURE", "ECM", 500),
    (0x200, "VEHICLE_STATUS", "TCM", 50),
    (0x201, "TRANSMISSION_STATUS", "TCM", 100),
    (0x300, "BODY_STATUS", "BCM", 200),
    (0x400, "DASHBOARD_STATUS", "IPC", 200),
    (0x500, "DIAGNOSTIC_STATUS", "DIAG", 1000),
]


def test_dbc_defines_expected_messages() -> None:
    db = load_database()

    actual = sorted((m.frame_id, m.name, m.senders[0], m.cycle_time) for m in db.messages)
    assert actual == EXPECTED_MESSAGES


def test_all_ids_are_standard_11_bit() -> None:
    for msg in load_database().messages:
        assert not msg.is_extended_frame
        assert msg.frame_id <= 0x7FF


def test_enum_signals_have_named_values() -> None:
    db = load_database()

    states = db.get_message_by_name("ENGINE_STATUS").get_signal_by_name("EngineState")
    assert list(states.choices.values()) == [
        "OFF",
        "STARTING",
        "IDLE",
        "ACCELERATING",
        "CRUISING",
        "DECELERATING",
        "OVERHEAT",
        "FAULT",
    ]
    selector = db.get_message_by_name("TRANSMISSION_STATUS").get_signal_by_name("GearSelector")
    assert list(selector.choices.values()) == ["P", "R", "N", "D"]


def make_dbc(
    path: Path,
    frame_id: int = 256,
    dlc: int = 8,
    sender: str = "ECM",
    cycle_ms: int = 100,
    counter: bool = True,
    checksum_start: int | None = 56,
) -> Path:
    """A one-message DBC that follows the project conventions unless told otherwise."""
    signals = [' SG_ EngineRPM : 0|16@1+ (0.25,0) [0|16383.75] "rpm" Vector__XXX']
    if counter:
        signals.append(' SG_ AliveCounter : 48|4@1+ (1,0) [0|15] "" Vector__XXX')
    if checksum_start is not None:
        signals.append(f' SG_ Checksum : {checksum_start}|8@1+ (1,0) [0|255] "" Vector__XXX')
    lines = [
        'VERSION ""',
        "NS_ :",
        "BS_:",
        "BU_: ECM",
        f"BO_ {frame_id} ENGINE_STATUS: {dlc} {sender}",
        *signals,
        "",
        'BA_DEF_ BO_ "GenMsgCycleTime" INT 0 65535;',
        'BA_DEF_DEF_ "GenMsgCycleTime" 0;',
    ]
    if cycle_ms:
        lines.append(f'BA_ "GenMsgCycleTime" BO_ {frame_id} {cycle_ms};')
    path.write_text("\n".join(lines) + "\n")
    return path


def test_validation_accepts_a_conforming_message(tmp_path: Path) -> None:
    db = load_database(make_dbc(tmp_path / "ok.dbc"))

    assert db.get_message_by_name("ENGINE_STATUS").cycle_time == 100


@pytest.mark.parametrize(
    ("override", "problem"),
    [
        ({"checksum_start": None}, "missing Checksum"),
        ({"checksum_start": 40}, "Checksum must occupy byte 7"),
        ({"counter": False}, "missing AliveCounter"),
        ({"dlc": 7, "checksum_start": 48, "counter": False}, "DLC must be 8"),
        ({"cycle_ms": 0}, "missing GenMsgCycleTime"),
        ({"sender": "Vector__XXX"}, "no sending node"),
        ({"frame_id": 0x80000100}, "standard 11-bit identifier"),
    ],
)
def test_validation_rejects_convention_violations(
    tmp_path: Path, override: dict, problem: str
) -> None:
    dbc = make_dbc(tmp_path / "bad.dbc", **override)

    with pytest.raises(DbcValidationError, match=problem):
        load_database(dbc)
