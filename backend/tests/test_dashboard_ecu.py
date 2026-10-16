import can
import pytest

from app.can.bus import BusFactory
from app.can.decoder import CanCodec
from app.ecus.dashboard import Severity
from app.simulation.simulator import Simulator

from .helpers import start_and_select_drive


def codes(sim: Simulator) -> dict[str, Severity]:
    return {w.code: w.severity for w in sim.dashboard.warnings}


def test_cluster_view_is_built_from_can(sim: Simulator) -> None:
    start_and_select_drive(sim)
    sim.driver.throttle = 60
    sim.run_for(12.0)

    view = sim.dashboard.view()

    assert view["speed_kmh"] == pytest.approx(sim.vehicle.speed_kmh, abs=1.0)
    assert view["gear"] == f"D{sim.transmission.gear}"
    assert view["engine_state"] == "ACCELERATING"
    assert view["sources_online"] == {"ECM": True, "TCM": True, "BCM": True}
    assert view["warnings"] == []
    assert view["master_severity"] == "NONE"


def test_view_is_empty_before_any_traffic(sim: Simulator) -> None:
    view = sim.dashboard.view()

    assert view["speed_kmh"] is None
    assert view["gear"] is None


def test_no_comm_lost_warning_during_startup_grace(sim: Simulator) -> None:
    sim.run_for(0.5)

    assert "CAN_COMM_LOST" not in codes(sim)


def test_odometer_integrates_received_speed(sim: Simulator) -> None:
    start_and_select_drive(sim)
    sim.driver.throttle = 70
    sim.run_for(20.0)

    assert sim.dashboard.odometer_km == pytest.approx(sim.vehicle.odometer_km, rel=0.02)
    assert sim.dashboard.odometer_km > 0.2


def test_door_open_is_info_when_stopped_and_warning_when_moving(sim: Simulator) -> None:
    start_and_select_drive(sim)
    sim.driver.doors_open["front_right"] = True
    sim.run_for(0.5)
    assert codes(sim)["DOOR_OPEN"] is Severity.INFO

    sim.driver.throttle = 50
    sim.run_for(4.0)
    assert codes(sim)["DOOR_OPEN"] is Severity.WARNING


def test_seatbelt_warning_escalates_with_speed(sim: Simulator) -> None:
    sim.driver.seatbelt_fastened = False
    start_and_select_drive(sim)
    sim.run_for(0.5)
    assert codes(sim)["SEATBELT"] is Severity.INFO

    sim.driver.throttle = 50
    sim.run_for(4.0)
    assert codes(sim)["SEATBELT"] is Severity.WARNING


def test_low_fuel_warning(sim: Simulator) -> None:
    sim.vehicle.fuel_l = 5.0  # 10 %
    sim.run_for(3.0)

    assert codes(sim)["LOW_FUEL"] is Severity.WARNING


def test_overheat_is_critical(sim: Simulator) -> None:
    sim.driver.ignition = True
    sim.run_for(1.5)
    sim.vehicle.coolant_c = 120.0
    sim.run_for(1.0)

    assert codes(sim)["ENGINE_OVERHEAT"] is Severity.CRITICAL
    assert sim.dashboard.master_severity is Severity.CRITICAL


def test_engine_fault_is_critical(sim: Simulator) -> None:
    sim.driver.ignition = True
    sim.run_for(1.5)
    sim.vehicle.fuel_l = 0.0
    sim.run_for(3.0)

    assert codes(sim)["ENGINE_FAULT"] is Severity.CRITICAL


def test_silent_ecu_raises_comm_lost_and_blanks_its_values(
    sim: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(now: float) -> None:
        raise RuntimeError("simulated TCM software fault")

    sim.run_for(2.0)
    monkeypatch.setattr(sim.transmission, "update", explode)
    sim.run_for(1.0)

    view = sim.dashboard.view()
    lost = [w for w in sim.dashboard.warnings if w.code == "CAN_COMM_LOST"]
    assert [w.message for w in lost] == ["Transmission ECU offline: CAN communication lost"]
    assert lost[0].severity is Severity.CRITICAL
    assert view["sources_online"]["TCM"] is False
    assert view["speed_kmh"] is None
    assert view["rpm"] is not None  # ECM still talking


def test_warnings_are_sorted_most_severe_first(sim: Simulator) -> None:
    sim.driver.ignition = True
    sim.driver.doors_open["rear_right"] = True
    sim.run_for(1.5)
    sim.vehicle.coolant_c = 120.0
    sim.run_for(1.0)

    severities = [w.severity for w in sim.dashboard.warnings]
    assert severities == sorted(severities, reverse=True)
    assert len(severities) >= 2


def test_dashboard_status_on_bus_carries_lamps(
    factory: BusFactory, sim: Simulator, codec: CanCodec
) -> None:
    sniffer: can.BusABC = factory.open()
    try:
        sim.driver.ignition = True
        sim.driver.doors_open["front_left"] = True
        sim.run_for(1.5)
        sim.vehicle.coolant_c = 120.0
        sim.run_for(1.0)

        latest = None
        while (frame := sniffer.recv(timeout=0)) is not None:
            decoded = codec.decode(frame)
            if decoded.name == "DASHBOARD_STATUS":
                latest = decoded.signals
    finally:
        sniffer.shutdown()

    assert latest is not None
    assert latest["WarnEngineOverheat"] == 1
    assert latest["WarnDoorOpen"] == 1
    assert latest["WarnLowFuel"] == 0
    assert latest["MasterSeverity"] == "CRITICAL"
