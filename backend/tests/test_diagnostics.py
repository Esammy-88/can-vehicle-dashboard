import json

import can

from app.can.bus import BusFactory
from app.can.decoder import CanCodec
from app.ecus import dtc
from app.monitoring.event_log import EventLog
from app.monitoring.watchdog import Watchdog
from app.simulation.faults import FaultType
from app.simulation.simulator import Simulator

# --- DTC encoding ---------------------------------------------------------------


def test_dtc_round_trip() -> None:
    for code in ("P0217", "P2299", "U0100", "U0401", "C1234", "B0001"):
        assert dtc.decode(dtc.encode(code)) == code
    assert dtc.encode("P0217") == 0x0217
    assert dtc.encode("U0100") == 0xC100


# --- Watchdog -------------------------------------------------------------------


def test_watchdog_online_timeout_and_recovery() -> None:
    wd = Watchdog({"ECM": "Engine ECU"}, timeout_s=1.5)

    first = wd.feed("ECM", "ENGINE_STATUS", 0, 0.0)
    assert first is not None and first.event == "ECU_ONLINE"
    assert wd.feed("ECM", "ENGINE_STATUS", 1, 0.1) is None
    assert wd.check(1.5) == []

    [timeout] = wd.check(1.7)
    assert timeout.event == "ECU_TIMEOUT"
    assert timeout.details() == {
        "ecu": "ECM",
        "last_message": "ENGINE_STATUS",
        "last_seen_s": 0.1,
        "timeout_s": 1.5,
    }
    assert wd.check(5.0) == []  # reported once

    back = wd.feed("ECM", "ENGINE_STATUS", 2, 6.0)
    assert back is not None and back.event == "ECU_ONLINE"
    assert wd.ecus["ECM"].timeouts == 1


def test_watchdog_flags_repeated_and_skipped_alive_counters() -> None:
    wd = Watchdog({"TCM": "Transmission ECU"})
    for counter in (3, 4, 4, 5, 9, 10):  # one repeat, one jump
        wd.feed("TCM", "VEHICLE_STATUS", counter, 0.0)

    assert wd.ecus["TCM"].counter_errors == 2


def test_watchdog_counter_wraps_at_16() -> None:
    wd = Watchdog({"TCM": "Transmission ECU"})
    for counter in (14, 15, 0, 1):
        wd.feed("TCM", "VEHICLE_STATUS", counter, 0.0)

    assert wd.ecus["TCM"].counter_errors == 0


# --- Diagnostic node --------------------------------------------------------------


def test_diag_node_reports_all_ecus_online(sim: Simulator) -> None:
    sim.run_for(3.0)

    view = sim.diagnostics.view(sim.time)

    assert {e["node"]: e["online"] for e in view["ecus"]} == {
        "ECM": True,
        "TCM": True,
        "BCM": True,
        "IPC": True,
    }
    assert view["active_dtcs"] == []
    assert view["last_frame_ago_s"] < 0.05
    assert all(e["counter_errors"] == 0 for e in view["ecus"])


def test_diagnostic_status_frame_on_bus(
    factory: BusFactory, sim: Simulator, codec: CanCodec
) -> None:
    sniffer: can.BusABC = factory.open()
    try:
        sim.faults.inject(FaultType.ECU_OFFLINE, "BCM")
        sim.run_for(4.0)
        latest = None
        while (frame := sniffer.recv(timeout=0)) is not None:
            decoded = codec.decode(frame)
            if decoded.name == "DIAGNOSTIC_STATUS":
                latest = decoded.signals
    finally:
        sniffer.shutdown()

    assert latest is not None
    assert (latest["EcmOnline"], latest["BcmOnline"]) == (1, 0)
    assert latest["ActiveDtcCount"] == 1
    assert dtc.decode(latest["LastDtc"]) == "U0140"


def test_multiple_ecm_codes_are_collected_from_rotation(sim: Simulator) -> None:
    sim.driver.ignition = True
    sim.run_for(1.5)
    sim.faults.inject(FaultType.SENSOR_FAILURE)
    sim.faults.inject(FaultType.HIGH_RPM)
    sim.run_for(3.0)

    codes = {r.code for r in sim.diagnostics.active.values()}
    assert {"P0118", "P0219"} <= codes


def test_dtc_history_survives_clearing_and_can_be_wiped(sim: Simulator) -> None:
    sim.driver.ignition = True
    sim.run_for(1.5)
    sim.faults.inject(FaultType.SENSOR_FAILURE)
    sim.run_for(2.0)
    sim.faults.clear(FaultType.SENSOR_FAILURE)
    sim.run_for(4.0)

    history = sim.diagnostics.view(sim.time)["dtc_history"]
    assert history[0]["code"] == "P0118"
    assert history[0]["cleared_at"] is not None
    assert history[0]["description"].startswith("Engine coolant temperature sensor")

    sim.diagnostics.clear_history()
    assert sim.diagnostics.view(sim.time)["dtc_history"] == []


# --- Event log --------------------------------------------------------------------


def test_event_log_writes_json_lines(tmp_path) -> None:
    log = EventLog(tmp_path)
    log.add("ENGINE_OVERHEAT", "CRITICAL", "ECM", "Engine overheat", 12.5, value=112)
    log.add("ECU_ONLINE", "INFO", "TCM", "TCM online", 13.0)

    lines = log.path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    assert len(lines) == 2
    assert first["event"] == "ENGINE_OVERHEAT"
    assert first["severity"] == "CRITICAL"
    assert first["details"] == {"value": 112}
    assert first["sim_time"] == 12.5
    assert first["timestamp"].endswith("+00:00")


def test_event_log_since_and_exports() -> None:
    log = EventLog()
    for i in range(3):
        log.add("E", "INFO", "SYSTEM", f"event {i}", float(i))

    assert [e["message"] for e in log.since(1)] == ["event 1", "event 2"]
    csv = log.to_csv().splitlines()
    assert csv[0] == "seq,timestamp,sim_time,severity,event,source,message,details"
    assert len(csv) == 4
    assert len(json.loads(log.to_json())) == 3


def test_simulation_logs_state_changes(sim: Simulator) -> None:
    sim.driver.ignition = True
    sim.run_for(2.0)

    events = [(e["event"], e["message"]) for e in sim.events.since(0)]
    assert ("ENGINE_STATE", "Engine OFF → STARTING") in events
    assert ("ENGINE_STATE", "Engine STARTING → IDLE") in events
    assert sum(1 for name, _ in events if name == "ECU_ONLINE") == 4
