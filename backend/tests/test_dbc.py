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


def test_validation_rejects_message_without_checksum(tmp_path: Path) -> None:
    dbc = tmp_path / "bad.dbc"
    dbc.write_text(
        'VERSION ""\n\nNS_ :\n\nBS_:\n\nBU_: ECM\n\n'
        "BO_ 256 ENGINE_STATUS: 8 ECM\n"
        ' SG_ EngineRPM : 0|16@1+ (0.25,0) [0|16383.75] "rpm" Vector__XXX\n'
        ' SG_ AliveCounter : 48|4@1+ (1,0) [0|15] "" Vector__XXX\n\n'
        'BA_DEF_ BO_ "GenMsgCycleTime" INT 0 65535;\n'
        'BA_DEF_DEF_ "GenMsgCycleTime" 0;\n'
        'BA_ "GenMsgCycleTime" BO_ 256 100;\n'
    )

    with pytest.raises(DbcValidationError, match="missing Checksum"):
        load_database(dbc)
