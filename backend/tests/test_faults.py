"""Each injected fault must be detected the way a real vehicle network would."""

import pytest

from app.ecus.engine import LIMP_TORQUE_LIMIT, EngineState
from app.simulation.faults import FaultError, FaultType
from app.simulation.simulator import Simulator

from .helpers import start_and_select_drive


@pytest.fixture
def driving(sim: Simulator) -> Simulator:
    start_and_select_drive(sim)
    sim.driver.throttle = 40
    sim.run_for(15.0)
    return sim


def warnings(sim: Simulator) -> set[str]:
    return {w.code for w in sim.dashboard.warnings}


def dtcs(sim: Simulator) -> set[str]:
    return {r.code for r in sim.diagnostics.active.values()}


def online(sim: Simulator) -> dict[str, bool]:
    return {n: w.online for n, w in sim.diagnostics.watchdog.ecus.items()}


def test_engine_overheat_enters_limp_mode_and_recovers(driving: Simulator) -> None:
    driving.faults.inject(FaultType.ENGINE_OVERHEAT)
    driving.run_for(40.0)

    assert driving.engine.state is EngineState.OVERHEAT
    assert driving.engine.torque_limit == LIMP_TORQUE_LIMIT
    assert "ENGINE_OVERHEAT" in warnings(driving)
    assert "P0217" in dtcs(driving)

    driving.faults.clear(FaultType.ENGINE_OVERHEAT)
    driving.run_for(40.0)
    assert driving.engine.state is not EngineState.OVERHEAT
    assert "P0217" not in dtcs(driving)


def test_low_fuel_leak(driving: Simulator) -> None:
    driving.faults.inject(FaultType.LOW_FUEL)
    driving.run_for(40.0)

    assert "LOW_FUEL" in warnings(driving)
    assert driving.vehicle.fuel_pct < 15


def test_sensor_failure_is_caught_by_plausibility_check(driving: Simulator) -> None:
    driving.faults.inject(FaultType.SENSOR_FAILURE)
    driving.run_for(3.0)

    assert driving.dashboard.view()["coolant_c"] == -40
    assert "P0118" in dtcs(driving)
    assert "CHECK_ENGINE" in warnings(driving)
    assert driving.engine.state is not EngineState.OVERHEAT  # substitute value, no false alarm

    driving.faults.clear(FaultType.SENSOR_FAILURE)
    driving.run_for(4.0)
    assert "P0118" not in dtcs(driving)
    assert "CHECK_ENGINE" not in warnings(driving)


def test_ecu_offline_is_detected_by_watchdog_and_recovers(driving: Simulator) -> None:
    start = driving.events.seq
    driving.faults.inject(FaultType.ECU_OFFLINE, "TCM")
    driving.run_for(1.0)
    assert online(driving)["TCM"] is True  # not before the 1.5 s timeout

    driving.run_for(1.0)
    assert online(driving)["TCM"] is False
    assert "U0101" in dtcs(driving)
    assert "CAN_COMM_LOST" in warnings(driving)
    timeout = next(e for e in driving.events.since(start) if e["event"] == "ECU_TIMEOUT")
    assert timeout["source"] == "TCM"
    assert timeout["details"]["last_message"] in {"VEHICLE_STATUS", "TRANSMISSION_STATUS"}
    assert timeout["details"]["timeout_s"] == 1.5
    assert "OFFLINE" in timeout["message"]

    driving.faults.clear(FaultType.ECU_OFFLINE, "TCM")
    driving.run_for(1.0)
    assert online(driving)["TCM"] is True
    assert "U0101" not in dtcs(driving)
    assert any(
        e["event"] == "ECU_ONLINE" and e["source"] == "TCM" for e in driving.events.since(start)
    )


def test_engine_ecu_offline_stalls_and_restarts_on_reboot(driving: Simulator) -> None:
    driving.faults.inject(FaultType.ECU_OFFLINE, "ECM")
    driving.run_for(3.0)
    assert not driving.vehicle.engine_running

    driving.faults.clear(FaultType.ECU_OFFLINE, "ECM")
    driving.run_for(2.0)
    assert driving.vehicle.engine_running
    assert driving.engine.state is not EngineState.FAULT


def test_can_timeout_keeps_the_ecu_online(driving: Simulator) -> None:
    driving.faults.inject(FaultType.CAN_TIMEOUT, "ENGINE_TEMPERATURE")
    driving.run_for(3.0)

    row = next(r for r in driving.monitor.stats(driving.time)["per_id"] if r["id"] == 0x101)
    assert row["timed_out"] is True
    assert online(driving)["ECM"] is True  # ENGINE_STATUS still flowing
    assert "CAN_COMM_LOST" in warnings(driving)
    assert driving.dashboard.view()["coolant_c"] is None

    driving.faults.clear(FaultType.CAN_TIMEOUT, "ENGINE_TEMPERATURE")
    driving.run_for(1.0)
    assert driving.dashboard.view()["coolant_c"] is not None


def test_transmission_overheat_limits_gears(driving: Simulator) -> None:
    driving.faults.inject(FaultType.TRANSMISSION_OVERHEAT)
    driving.run_for(30.0)

    assert driving.transmission.overtemp
    assert driving.transmission.gear <= 3
    assert "TRANSMISSION_FAULT" in warnings(driving)
    assert "P0218" in dtcs(driving)


def test_stuck_throttle_is_overridden_by_brake(driving: Simulator) -> None:
    driving.faults.inject(FaultType.STUCK_THROTTLE)
    driving.driver.throttle = 0
    driving.run_for(1.0)
    assert driving.engine.throttle_cmd >= 40  # pedal released, but the sensor is stuck

    driving.driver.brake = 60
    driving.run_for(1.0)
    assert driving.engine.brake_override
    assert driving.engine.throttle_cmd == 0
    assert "P2299" in dtcs(driving)


def test_invalid_frames_are_counted_and_ignored(driving: Simulator) -> None:
    driving.faults.inject(FaultType.INVALID_CAN)
    driving.run_for(2.0)

    errors = driving.monitor.errors_by_type
    assert errors["CHECKSUM"] > 0 and errors["BAD_DLC"] > 0 and errors["UNKNOWN_ID"] > 0
    assert "U0401" in dtcs(driving)
    assert driving.engine.rx_errors > 0
    assert driving.dashboard.view()["rpm"] < 6000  # the corrupted 3000 rpm frames were ignored

    driving.faults.clear(FaultType.INVALID_CAN)
    before = sum(errors.values())
    driving.run_for(2.0)
    assert sum(driving.monitor.errors_by_type.values()) == before
    assert "U0401" not in dtcs(driving)


def test_bus_interruption_silences_everyone(driving: Simulator) -> None:
    driving.faults.inject(FaultType.BUS_INTERRUPTION)
    frames_before = driving.monitor.total_frames
    driving.run_for(2.0)

    assert driving.monitor.total_frames == frames_before
    assert not any(online(driving).values())
    assert dtcs(driving) == {"U0001"}
    assert driving.dashboard.view()["speed_kmh"] is None

    driving.faults.clear(FaultType.BUS_INTERRUPTION)
    driving.run_for(1.0)
    assert all(online(driving).values())
    assert "U0001" not in dtcs(driving)


def test_high_rpm(driving: Simulator) -> None:
    driving.faults.inject(FaultType.HIGH_RPM)
    driving.run_for(2.0)

    assert driving.dashboard.view()["rpm"] > 6500
    assert "HIGH_RPM" in warnings(driving)
    assert "P0219" in dtcs(driving)


def test_targeted_fault_requires_valid_target(sim: Simulator) -> None:
    with pytest.raises(FaultError):
        sim.faults.inject(FaultType.ECU_OFFLINE)
    with pytest.raises(FaultError):
        sim.faults.inject(FaultType.CAN_TIMEOUT, "NOT_A_MESSAGE")


def test_inject_is_idempotent_and_clear_all_undoes_everything(sim: Simulator) -> None:
    sim.faults.inject(FaultType.ENGINE_OVERHEAT)
    sim.faults.inject(FaultType.ENGINE_OVERHEAT)
    sim.faults.inject(FaultType.ECU_OFFLINE, "BCM")
    sim.faults.inject(FaultType.BUS_INTERRUPTION)
    assert len(sim.faults.active) == 3

    assert sim.faults.clear_all() == 3
    assert not sim.faults.active
    assert not sim.vehicle.cooling_failure
    assert not sim.disabled
    assert not sim.bus_down


def test_faults_are_logged(sim: Simulator) -> None:
    sim.faults.inject(FaultType.HIGH_RPM)
    sim.faults.clear(FaultType.HIGH_RPM)

    events = [e["event"] for e in sim.events.since(0)]
    assert events[-2:] == ["FAULT_INJECTED", "FAULT_CLEARED"]
