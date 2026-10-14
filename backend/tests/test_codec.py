import can
import pytest

from app.can.decoder import CanCodec, CanEncodeError
from app.can.frames import FrameError, compute_checksum

SAMPLE_SIGNALS = {
    "ENGINE_STATUS": {
        "EngineRPM": 2450.0,
        "EngineLoad": 42.5,
        "ThrottlePosition": 30.0,
        "EngineRunning": 1,
        "EngineState": "CRUISING",
    },
    "ENGINE_TEMPERATURE": {"CoolantTemp": 91, "OilTemp": 104},
    "VEHICLE_STATUS": {"VehicleSpeed": 82.37, "BrakeSwitch": 0},
    "TRANSMISSION_STATUS": {
        "GearSelector": "D",
        "CurrentGear": 4,
        "TransTemp": 78,
        "TransFault": 0,
        "ShiftInProgress": 1,
    },
    "BODY_STATUS": {
        "FuelLevel": 67.5,
        "Headlights": "LOW",
        "TurnIndicator": "HAZARD",
        "DoorFrontLeftOpen": 1,
        "DoorFrontRightOpen": 0,
        "DoorRearLeftOpen": 0,
        "DoorRearRightOpen": 1,
        "SeatbeltFastened": 1,
        "BrakeLights": 0,
    },
    "DASHBOARD_STATUS": {
        "WarnLowFuel": 0,
        "WarnEngineOverheat": 1,
        "WarnHighOilTemp": 0,
        "WarnCanCommLost": 0,
        "WarnEngineFault": 0,
        "WarnTransFault": 0,
        "WarnDoorOpen": 1,
        "WarnSeatbelt": 0,
        "MasterSeverity": "CRITICAL",
        "Odometer": 12345.6,
    },
    "DIAGNOSTIC_STATUS": {
        "EcmOnline": 1,
        "TcmOnline": 1,
        "BcmOnline": 0,
        "IpcOnline": 1,
        "ActiveDtcCount": 2,
        "LastDtc": 0x0217,
    },
}


def test_samples_cover_every_message(codec: CanCodec) -> None:
    assert set(SAMPLE_SIGNALS) == {m.name for m in codec.messages}


@pytest.mark.parametrize("name", sorted(SAMPLE_SIGNALS))
def test_encode_decode_round_trip(codec: CanCodec, name: str) -> None:
    signals = SAMPLE_SIGNALS[name]

    frame = codec.encode(name, signals, counter=5)
    decoded = codec.decode(frame)

    assert decoded.ok, decoded.error_detail
    assert decoded.name == name
    assert decoded.dlc == 8
    assert decoded.signals["AliveCounter"] == 5
    for key, value in signals.items():
        assert decoded.signals[key] == pytest.approx(value), key


def test_engine_rpm_byte_layout(codec: CanCodec) -> None:
    # 2450 rpm / 0.25 = 9800 = 0x2648, little-endian in bytes 0-1.
    frame = codec.encode("ENGINE_STATUS", SAMPLE_SIGNALS["ENGINE_STATUS"])

    assert frame.arbitration_id == 0x100
    assert not frame.is_extended_id
    assert frame.data[0:2] == bytes([0x48, 0x26])


def test_temperature_offset_scaling(codec: CanCodec) -> None:
    frame = codec.encode("ENGINE_TEMPERATURE", {"CoolantTemp": -40, "OilTemp": 0})

    assert frame.data[0] == 0  # -40 degC is raw 0
    assert frame.data[1] == 40  # 0 degC is raw 40


def test_checksum_is_written_to_byte_7(codec: CanCodec) -> None:
    frame = codec.encode("VEHICLE_STATUS", SAMPLE_SIGNALS["VEHICLE_STATUS"])

    assert frame.data[7] == compute_checksum(0x200, frame.data)


def test_alive_counter_wraps_at_16(codec: CanCodec) -> None:
    frame = codec.encode("VEHICLE_STATUS", SAMPLE_SIGNALS["VEHICLE_STATUS"], counter=17)

    assert codec.decode(frame).signals["AliveCounter"] == 1


def test_encode_rejects_out_of_range_value(codec: CanCodec) -> None:
    signals = {**SAMPLE_SIGNALS["TRANSMISSION_STATUS"], "CurrentGear": 9}

    with pytest.raises(CanEncodeError, match="CurrentGear"):
        codec.encode("TRANSMISSION_STATUS", signals)


def test_encode_rejects_missing_signal(codec: CanCodec) -> None:
    with pytest.raises(CanEncodeError, match="BrakeSwitch"):
        codec.encode("VEHICLE_STATUS", {"VehicleSpeed": 10})


def test_encode_rejects_unknown_message(codec: CanCodec) -> None:
    with pytest.raises(CanEncodeError, match="Unknown message"):
        codec.encode("NOT_A_MESSAGE", {})


def test_decode_unknown_id(codec: CanCodec) -> None:
    decoded = codec.decode(can.Message(arbitration_id=0x7FF, data=bytes(8), is_extended_id=False))

    assert decoded.error is FrameError.UNKNOWN_ID
    assert decoded.name is None


def test_decode_extended_id_is_not_confused_with_standard(codec: CanCodec) -> None:
    decoded = codec.decode(can.Message(arbitration_id=0x100, data=bytes(8), is_extended_id=True))

    assert decoded.error is FrameError.UNKNOWN_ID


def test_decode_wrong_dlc(codec: CanCodec) -> None:
    decoded = codec.decode(can.Message(arbitration_id=0x100, data=bytes(4), is_extended_id=False))

    assert decoded.error is FrameError.BAD_DLC
    assert decoded.name == "ENGINE_STATUS"


def test_decode_detects_corrupted_payload(codec: CanCodec) -> None:
    frame = codec.encode("ENGINE_STATUS", SAMPLE_SIGNALS["ENGINE_STATUS"])
    frame.data[0] ^= 0x01

    decoded = codec.decode(frame)

    assert decoded.error is FrameError.CHECKSUM
    assert decoded.signals  # still decoded, so the monitor can show what arrived


def test_decode_detects_payload_replayed_under_other_id(codec: CanCodec) -> None:
    frame = codec.encode("ENGINE_STATUS", SAMPLE_SIGNALS["ENGINE_STATUS"])
    replayed = can.Message(arbitration_id=0x101, data=frame.data, is_extended_id=False)

    assert codec.decode(replayed).error is FrameError.CHECKSUM


def test_decode_error_frame(codec: CanCodec) -> None:
    decoded = codec.decode(can.Message(is_error_frame=True))

    assert decoded.error is FrameError.ERROR_FRAME
