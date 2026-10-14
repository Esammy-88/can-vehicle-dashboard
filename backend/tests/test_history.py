import pytest

from app.monitoring.history import SAMPLE_INTERVAL_S, TelemetryHistory
from app.simulation.simulator import Simulator

from .helpers import start_and_select_drive


def test_samples_at_fixed_interval(sim: Simulator) -> None:
    sim.run_for(2.0)

    samples = sim.history.since(0)
    times = [s["t"] for s in samples]

    assert len(samples) == pytest.approx(2.0 / SAMPLE_INTERVAL_S, abs=1)
    assert all(
        b - a == pytest.approx(SAMPLE_INTERVAL_S) for a, b in zip(times, times[1:], strict=False)
    )


def test_samples_hold_can_decoded_values(sim: Simulator) -> None:
    start_and_select_drive(sim)
    sim.driver.throttle = 60
    sim.run_for(8.0)

    last = sim.history.since(0)[-1]

    assert set(last) == {
        "seq",
        "t",
        "can_rate",
        "speed_kmh",
        "rpm",
        "coolant_c",
        "oil_c",
        "fuel_pct",
        "engine_load",
    }
    assert last["speed_kmh"] == pytest.approx(
        sim.dashboard.view()["speed_kmh"], abs=2.0
    )  # <= 0.2 s old
    assert last["rpm"] > 1000
    assert last["can_rate"] == 52.0


def test_since_returns_only_newer_samples(sim: Simulator) -> None:
    sim.run_for(1.0)
    seq = sim.history.seq
    sim.run_for(1.0)

    newer = sim.history.since(seq)

    assert newer and all(s["seq"] > seq for s in newer)


def test_window_limits_by_time(sim: Simulator) -> None:
    sim.run_for(5.0)

    window = sim.history.window(1.0)

    assert window[-1]["t"] - window[0]["t"] <= 1.0
    assert len(window) == pytest.approx(1.0 / SAMPLE_INTERVAL_S + 1, abs=1)


def test_history_is_bounded() -> None:
    h = TelemetryHistory()
    view = dict.fromkeys(["speed_kmh", "rpm", "coolant_c", "oil_c", "fuel_pct", "engine_load"], 0)
    for i in range(5000):
        h.sample(i * SAMPLE_INTERVAL_S, view, 0.0)

    assert len(h.since(0)) == 1500
