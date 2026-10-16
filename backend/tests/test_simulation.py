"""Integration tests: the full ECU network observed from a passive bus sniffer."""

from collections import Counter, defaultdict

import can
import pytest

from app.can.bus import BusFactory
from app.can.decoder import CanCodec
from app.can.frames import DecodedFrame
from app.simulation.simulator import Simulator
from app.simulation.vehicle import Headlights, TurnIndicator

from .helpers import start_and_select_drive


@pytest.fixture
def sniffer(factory: BusFactory, sim: Simulator) -> can.BusABC:
    bus = factory.open()
    yield bus
    bus.shutdown()


def drain(bus: can.BusABC, codec: CanCodec) -> list[DecodedFrame]:
    frames = []
    while (frame := bus.recv(timeout=0)) is not None:
        frames.append(codec.decode(frame))
    return frames


def test_messages_are_sent_at_dbc_cycle_times(
    sim: Simulator, sniffer: can.BusABC, codec: CanCodec
) -> None:
    sim.run_for(1.0)
    drain(sniffer, codec)  # discard start-up so we measure a steady-state window
    sim.run_for(2.0)

    counts = Counter(f.name for f in drain(sniffer, codec))

    assert counts == {
        "VEHICLE_STATUS": 40,  # 50 ms
        "ENGINE_STATUS": 20,  # 100 ms
        "TRANSMISSION_STATUS": 20,  # 100 ms
        "BODY_STATUS": 10,  # 200 ms
        "DASHBOARD_STATUS": 10,  # 200 ms
        "DIAGNOSTIC_STATUS": 2,  # 1000 ms
        "ENGINE_TEMPERATURE": 4,  # 500 ms
    }


def test_all_traffic_is_valid_with_incrementing_alive_counters(
    sim: Simulator, sniffer: can.BusABC, codec: CanCodec
) -> None:
    start_and_select_drive(sim)
    sim.driver.throttle = 80
    sim.run_for(10.0)

    frames = drain(sniffer, codec)
    counters: dict[str, list[int]] = defaultdict(list)
    for f in frames:
        assert f.ok, f"{f.name}: {f.error} {f.error_detail}"
        counters[f.name].append(f.signals["AliveCounter"])

    for name, seq in counters.items():
        steps = {(b - a) % 16 for a, b in zip(seq, seq[1:], strict=False)}
        assert steps == {1}, name


def test_can_traffic_reflects_the_vehicle(
    sim: Simulator, sniffer: can.BusABC, codec: CanCodec
) -> None:
    start_and_select_drive(sim)
    sim.driver.throttle = 60
    sim.driver.headlights = Headlights.LOW
    sim.driver.turn_indicator = TurnIndicator.LEFT
    sim.driver.doors_open["rear_left"] = True
    sim.driver.seatbelt_fastened = False
    sim.run_for(12.0)

    latest = {f.name: f.signals for f in drain(sniffer, codec)}

    assert latest["VEHICLE_STATUS"]["VehicleSpeed"] == pytest.approx(sim.vehicle.speed_kmh, abs=1.0)
    assert latest["VEHICLE_STATUS"]["VehicleSpeed"] > 50
    assert latest["ENGINE_STATUS"]["EngineState"] == "ACCELERATING"
    assert latest["ENGINE_STATUS"]["EngineRunning"] == 1
    assert latest["ENGINE_STATUS"]["ThrottlePosition"] == 60
    assert latest["TRANSMISSION_STATUS"]["GearSelector"] == "D"
    assert latest["TRANSMISSION_STATUS"]["CurrentGear"] >= 2
    assert latest["ENGINE_TEMPERATURE"]["CoolantTemp"] > 20
    body = latest["BODY_STATUS"]
    assert body["Headlights"] == "LOW"
    assert body["TurnIndicator"] == "LEFT"
    assert body["DoorRearLeftOpen"] == 1
    assert body["SeatbeltFastened"] == 0
    assert body["BrakeLights"] == 0
    assert 0 < body["FuelLevel"] <= 100


def test_brake_pedal_drives_brake_lights_and_brake_switch(
    sim: Simulator, sniffer: can.BusABC, codec: CanCodec
) -> None:
    sim.driver.brake = 40
    sim.run_for(0.5)

    latest = {f.name: f.signals for f in drain(sniffer, codec)}

    assert latest["BODY_STATUS"]["BrakeLights"] == 1
    assert latest["VEHICLE_STATUS"]["BrakeSwitch"] == 1


def test_same_seed_gives_identical_runs(factory: BusFactory, codec: CanCodec) -> None:
    results = []
    for _ in range(2):
        with Simulator(factory, codec, seed=7) as s:
            start_and_select_drive(s)
            s.driver.throttle = 70
            s.run_for(8.0)
            results.append((s.vehicle.speed_ms, s.vehicle.engine_rpm, s.transmission.gear))

    assert results[0] == results[1]


def test_crashing_ecu_is_isolated(
    sim: Simulator, sniffer: can.BusABC, codec: CanCodec, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(now: float) -> None:
        raise RuntimeError("simulated BCM software fault")

    monkeypatch.setattr(sim.body, "update", explode)
    sim.driver.ignition = True
    sim.run_for(1.0)

    names = {f.name for f in drain(sniffer, codec)}

    assert sim.crashed == {"BCM"}
    assert "BODY_STATUS" not in names
    assert {"ENGINE_STATUS", "VEHICLE_STATUS"} <= names


def test_engine_falls_back_when_tcm_goes_silent(
    sim: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    start_and_select_drive(sim)
    sim.driver.throttle = 50
    sim.run_for(5.0)
    assert sim.engine.vehicle_speed_kmh > 10

    def explode(now: float) -> None:
        raise RuntimeError("simulated TCM software fault")

    monkeypatch.setattr(sim.transmission, "update", explode)
    sim.run_for(0.5)

    assert sim.engine.latest("VEHICLE_STATUS", sim.time) is None
    assert sim.engine.vehicle_speed_kmh == 0.0
