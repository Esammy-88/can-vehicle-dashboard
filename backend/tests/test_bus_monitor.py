import can
import pytest

from app.can.bus import BusFactory
from app.can.decoder import CanCodec
from app.monitoring.bus_monitor import BITRATE_BPS, BusMonitor, frame_bits
from app.simulation.simulator import Simulator

# Frames per second each message should produce, from its DBC cycle time.
EXPECTED_RATES = {
    0x100: 10.0,
    0x101: 2.0,
    0x200: 20.0,
    0x201: 10.0,
    0x300: 5.0,
    0x400: 5.0,
    0x500: 1.0,
}


@pytest.fixture
def monitor(factory: BusFactory, codec: CanCodec):
    m = BusMonitor(factory.open(), codec)
    tx = factory.open()
    yield m, tx
    m.bus.shutdown()
    tx.shutdown()


def test_frame_bits_for_full_frame() -> None:
    assert frame_bits(8) == 111
    assert frame_bits(0) == 47


def test_rates_match_dbc_cycle_times(sim: Simulator) -> None:
    sim.run_for(3.0)

    stats = sim.monitor.stats(sim.time)

    assert {row["id"]: row["rate"] for row in stats["per_id"]} == EXPECTED_RATES
    assert stats["messages_per_s"] == sum(EXPECTED_RATES.values())


def test_per_ecu_rates_and_active_nodes(sim: Simulator) -> None:
    sim.run_for(3.0)

    stats = sim.monitor.stats(sim.time)

    assert {row["ecu"]: row["rate"] for row in stats["per_ecu"]} == {
        "ECM": 12.0,
        "TCM": 30.0,
        "BCM": 5.0,
        "IPC": 5.0,
        "DIAG": 1.0,
    }
    assert stats["active_nodes"] == ["BCM", "DIAG", "ECM", "IPC", "TCM"]


def test_bus_load(sim: Simulator) -> None:
    sim.run_for(3.0)

    stats = sim.monitor.stats(sim.time)

    expected = 53 * 111 / BITRATE_BPS * 100
    assert stats["bus_load_pct"] == pytest.approx(expected, abs=0.01)


def test_frames_are_decoded_records(sim: Simulator) -> None:
    sim.run_for(0.5)

    frame = next(f for f in reversed(sim.monitor.frames) if f["name"] == "ENGINE_STATUS")

    assert frame["id"] == 0x100
    assert frame["sender"] == "ECM"
    assert frame["dlc"] == 8
    assert len(frame["data"].split(" ")) == 8
    assert frame["error"] is None
    assert "EngineRPM" in frame["signals"]


def test_bad_frames_are_counted_by_type(monitor, codec: CanCodec) -> None:
    m, tx = monitor
    good = codec.encode(
        "ENGINE_TEMPERATURE",
        {"CoolantTemp": 90, "OilTemp": 95, "EngineDtc": 0, "EngineDtcCount": 0},
    )
    corrupted = can.Message(arbitration_id=0x101, data=bytes(8), is_extended_id=False)
    unknown = can.Message(arbitration_id=0x7AB, data=bytes(8), is_extended_id=False)
    for frame in (good, corrupted, unknown):
        tx.send(frame)

    m.poll(0.1)
    stats = m.stats(0.1)

    assert stats["errors"] == 2
    assert stats["errors_by_type"] == {"CHECKSUM": 1, "UNKNOWN_ID": 1}
    assert [f["error"] for f in m.frames] == [None, "CHECKSUM", "UNKNOWN_ID"]
    assert m.frames[-1]["sender"] == "UNKNOWN"


def test_timeout_is_counted_once_and_clears_on_recovery(monitor, codec: CanCodec) -> None:
    m, tx = monitor
    frame = codec.encode(
        "ENGINE_TEMPERATURE",
        {"CoolantTemp": 90, "OilTemp": 95, "EngineDtc": 0, "EngineDtcCount": 0},
    )  # 500 ms cycle

    tx.send(frame)
    m.poll(0.0)
    m.poll(1.4)
    assert m.timeouts == 0

    m.poll(1.6)  # > 3 cycles without a frame
    m.poll(3.0)
    row = next(r for r in m.stats(3.0)["per_id"] if r["id"] == 0x101)
    assert m.timeouts == 1
    assert row["timed_out"] is True

    tx.send(frame)
    m.poll(3.1)
    row = next(r for r in m.stats(3.1)["per_id"] if r["id"] == 0x101)
    assert row["timed_out"] is False
    assert row["timeouts"] == 1


def test_invalid_frames_do_not_keep_a_message_alive(monitor, codec: CanCodec) -> None:
    m, tx = monitor
    tx.send(
        codec.encode(
            "ENGINE_TEMPERATURE",
            {"CoolantTemp": 90, "OilTemp": 95, "EngineDtc": 0, "EngineDtcCount": 0},
        )
    )
    m.poll(0.0)

    # A rogue node keeps sending a truncated frame with the same ID.
    for step in range(1, 31):
        tx.send(can.Message(arbitration_id=0x101, data=bytes(4), is_extended_id=False))
        m.poll(step * 0.1)

    row = next(r for r in m.stats(3.0)["per_id"] if r["id"] == 0x101)
    assert row["timed_out"] is True
    assert m.timeouts == 1  # timed out once, never "restored" by garbage
    assert [e["event"] for e in m.edges] == ["MESSAGE_TIMEOUT"]
    assert row["errors"] == 30


def test_crashed_ecu_shows_up_as_timeouts(sim: Simulator, monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(now: float) -> None:
        raise RuntimeError("simulated BCM fault")

    sim.run_for(1.0)
    monkeypatch.setattr(sim.body, "update", explode)
    sim.run_for(2.0)

    stats = sim.monitor.stats(sim.time)
    body = next(r for r in stats["per_id"] if r["name"] == "BODY_STATUS")
    assert body["timed_out"] is True
    assert "BCM" not in stats["active_nodes"]


def test_frames_since_and_ring_buffer(monitor, codec: CanCodec) -> None:
    m, tx = monitor
    m.frames = type(m.frames)(maxlen=5)
    for i in range(8):
        tx.send(codec.encode("VEHICLE_STATUS", {"VehicleSpeed": i, "BrakeSwitch": 0}, counter=i))
    m.poll(0.1)

    assert [f["seq"] for f in m.frames] == [4, 5, 6, 7, 8]
    assert [f["seq"] for f in m.frames_since(6)] == [7, 8]
    assert m.total_frames == 8
