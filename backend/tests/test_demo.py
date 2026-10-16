from app.ecus.engine import EngineState
from app.simulation.demo import DemoDirector, DemoStep
from app.simulation.simulator import Simulator
from app.simulation.vehicle import Selector

DEMO_LIMIT_S = 240.0


def play(sim: Simulator, director: DemoDirector, limit_s: float = DEMO_LIMIT_S) -> dict:
    """Run the demo to the end, recording what the cluster showed along the way."""
    seen = {"max_speed": 0.0, "max_gear": 0, "min_coolant": 999.0, "max_coolant": 0.0}
    while director.active and sim.time < limit_s:
        sim.step()
        director.step()
        view = sim.dashboard.view()
        seen["max_speed"] = max(seen["max_speed"], view["speed_kmh"] or 0.0)
        seen["max_gear"] = max(seen["max_gear"], view["current_gear"] or 0)
        if view["coolant_c"] is not None:
            seen["min_coolant"] = min(seen["min_coolant"], view["coolant_c"])
            seen["max_coolant"] = max(seen["max_coolant"], view["coolant_c"])
    return seen


def test_demo_runs_the_whole_sequence(sim: Simulator) -> None:
    director = DemoDirector(sim)

    seen = play(sim, director)

    assert director.finished
    assert director.timed_out == []
    elapsed = director.status()["elapsed_s"]
    sim.run_for(1.0)
    assert director.status()["elapsed_s"] == elapsed  # frozen once finished
    assert seen["max_speed"] >= 120
    assert seen["max_gear"] >= 4
    assert seen["max_coolant"] - seen["min_coolant"] > 50
    # Every step ran, in order, and the system reacted the way the captions say.
    events = [(e["event"], e["message"]) for e in sim.events.recent(1000)]
    names = [name for name, _ in events]
    steps = [msg for name, msg in events if name == "DEMO_STEP"]
    assert len(steps) == len(director.steps)
    expected_order = [
        "DEMO_START",
        "ENGINE_STATE",  # OFF -> STARTING
        "FAULT_INJECTED",
        "ENGINE_OVERHEAT",
        "DTC_SET",  # P0217
        "CAN_COMM_LOST",
        "ECU_TIMEOUT",
        "ECU_ONLINE",
        "FAULT_CLEARED",
        "DTC_CLEARED",
        "DEMO_COMPLETE",
    ]
    position = 0
    for name in names:
        if position < len(expected_order) and name == expected_order[position]:
            position += 1
    assert position == len(expected_order), f"missing {expected_order[position:]}"


def test_demo_ends_healthy(sim: Simulator) -> None:
    director = DemoDirector(sim)

    play(sim, director)

    view = sim.dashboard.view()
    assert sim.faults.active == {}
    assert view["warnings"] == []
    assert view["engine_state"] == EngineState.IDLE.value
    assert view["selector"] == Selector.P.value
    assert all(view["sources_online"].values())
    assert {code for _, code in sim.diagnostics.active} == set()


def test_stopping_undoes_the_demo_faults(sim: Simulator) -> None:
    director = DemoDirector(sim)
    while director.current is not None and director.current.title != "ECU timeout reported":
        sim.step()
        director.step()
    assert len(sim.faults.active) == 2

    director.stop()

    assert not director.active
    assert sim.faults.active == {}
    assert sim.driver.throttle == 0.0
    assert sim.events.recent(1)[0]["event"] == "DEMO_STOPPED"
    director.step()  # a stopped demo does nothing
    assert director.stopped


def test_step_timeout_moves_on(sim: Simulator) -> None:
    never = DemoStep("Never", "Waits forever", lambda s: None, done=lambda s: False, timeout_s=1.0)
    director = DemoDirector(sim, [never])

    play(sim, director, limit_s=5.0)

    assert director.finished
    assert director.timed_out == ["Never"]
    assert any(e["event"] == "DEMO_STEP_TIMEOUT" for e in sim.events.recent(10))


def test_step_holds_after_its_condition(sim: Simulator) -> None:
    steps = [DemoStep("A", "a", lambda s: None, hold_s=2.0), DemoStep("B", "b", lambda s: None)]
    director = DemoDirector(sim, steps)

    play(sim, director, limit_s=1.5)
    assert director.current is steps[0]  # condition met at once, still holding
    play(sim, director, limit_s=5.0)

    assert director.finished
    assert 2.0 <= sim.time < 2.1


def test_status_reports_progress(sim: Simulator) -> None:
    director = DemoDirector(sim)

    status = director.status()

    assert status["active"] is True
    assert status["step"] == 1
    assert status["total"] == len(director.steps)
    assert status["title"] == "Start vehicle"
    assert status["caption"]
