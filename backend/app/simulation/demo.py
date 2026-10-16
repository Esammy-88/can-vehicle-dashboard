"""Demo Mode: a scripted drive that shows every part of the system in turn.

The director plays the driver and the test engineer: it moves the pedals and
the selector, injects and clears faults, and waits for the ECUs to react
before moving on. It never touches the plant or the ECUs directly, so what the
dashboard shows is exactly what the CAN network reported. Steps advance on
conditions observed through CAN (engine state, warnings, DTCs), not on fixed
timers, so the sequence stays correct at any simulation speed. Each step also
has a timeout, so a demo can never hang.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.ecus.engine import EngineState
from app.simulation.faults import FaultType
from app.simulation.vehicle import Selector

if TYPE_CHECKING:
    from app.simulation.simulator import Simulator

Check = Callable[["Simulator"], bool]
Action = Callable[["Simulator"], None]

OFFLINE_ECU = "TCM"  # the ECU whose communication the demo interrupts


@dataclass(frozen=True)
class DemoStep:
    title: str
    caption: str  # one sentence shown to the viewer while the step runs
    enter: Action
    done: Check = lambda sim: True
    hold_s: float = 0.0  # keep showing the result this long once `done` is true
    timeout_s: float = 30.0


# --- helpers used by the steps ----------------------------------------------


def _drive(**inputs: Any) -> Action:
    def apply(sim: Simulator) -> None:
        for name, value in inputs.items():
            setattr(sim.driver, name, value)

    return apply


def _do(*actions: Action) -> Action:
    def apply(sim: Simulator) -> None:
        for action in actions:
            action(sim)

    return apply


def _inject(kind: FaultType, target: str | None = None) -> Action:
    return lambda sim: sim.faults.inject(kind, target) and None


def _clear(kind: FaultType, target: str | None = None) -> Action:
    return lambda sim: sim.faults.clear(kind, target) and None


def _cluster(sim: Simulator, signal: str) -> Any:
    """What the instrument cluster decoded from CAN (None while the data is missing)."""
    return sim.dashboard.view()[signal]


def _speed(sim: Simulator) -> float:
    return _cluster(sim, "speed_kmh") or 0.0


def _warning(sim: Simulator, code: str) -> bool:
    return any(w.code == code for w in sim.dashboard.warnings)


def _dtc(sim: Simulator, code: str) -> bool:
    return any(c == code for _, c in sim.diagnostics.active)


def _engine(state: EngineState) -> Check:
    return lambda sim: _cluster(sim, "engine_state") == state.value


def _selector(selector: Selector) -> Check:
    return lambda sim: _cluster(sim, "selector") == selector.value


def build_steps() -> list[DemoStep]:
    """The sequence from spec §28, one step per thing the viewer should notice."""
    return [
        DemoStep(
            "Start vehicle",
            "Ignition on: the engine ECU cranks the engine (OFF → STARTING → IDLE).",
            _drive(ignition=True, gear_selector=Selector.P),
            done=_engine(EngineState.IDLE),
            hold_s=3.0,
        ),
        DemoStep(
            "Select Drive",
            "Foot on the brake releases the shift lock; the TCM engages Drive.",
            _drive(brake=40.0, gear_selector=Selector.D),
            done=_selector(Selector.D),
            hold_s=1.5,
        ),
        DemoStep(
            "Accelerate",
            "Throttle 60 %: the ECM opens the electronic throttle and the car pulls away.",
            _drive(brake=0.0, throttle=60.0),
            done=lambda sim: _speed(sim) >= 40.0,
        ),
        DemoStep(
            "Gear changes",
            "The TCM upshifts as speed rises; torque dips briefly during each shift.",
            _drive(throttle=60.0),
            done=lambda sim: (_cluster(sim, "current_gear") or 0) >= 4 and _speed(sim) >= 90.0,
            timeout_s=40.0,
        ),
        DemoStep(
            "Speed increases",
            "Heavy throttle up to motorway speed; engine load and coolant temperature rise.",
            _drive(throttle=80.0),
            done=lambda sim: _speed(sim) >= 120.0,
            timeout_s=40.0,
        ),
        DemoStep(
            "Cruise",
            "Light throttle holds a steady 120 km/h: the engine ECU reports CRUISING.",
            _drive(throttle=38.0),
            done=_engine(EngineState.CRUISING),
            hold_s=6.0,
        ),
        DemoStep(
            "Brake",
            "Throttle released, brake at 35 %: brake lights on, the car slows down.",
            _drive(throttle=0.0, brake=35.0),
            done=lambda sim: _speed(sim) < 1.0,
            timeout_s=45.0,
        ),
        DemoStep(
            "Vehicle stopped",
            "Stopped and shifted to Park; the engine returns to idle.",
            _drive(gear_selector=Selector.P),
            done=_selector(Selector.P),
            hold_s=3.0,
        ),
        DemoStep(
            "Inject a fault",
            "Fault injected: cooling system failure. Coolant temperature starts to climb.",
            _do(_drive(brake=0.0), _inject(FaultType.ENGINE_OVERHEAT)),
            done=lambda sim: _warning(sim, "ENGINE_OVERHEAT"),
            timeout_s=60.0,
        ),
        DemoStep(
            "Fault detected",
            "The ECM enters OVERHEAT limp mode and sets DTC P0217; the cluster warns the driver.",
            lambda sim: None,
            done=lambda sim: _engine(EngineState.OVERHEAT)(sim) and _dtc(sim, "P0217"),
            hold_s=5.0,
            timeout_s=60.0,
        ),
        DemoStep(
            "ECU communication interrupted",
            f"The transmission ECU ({OFFLINE_ECU}) loses power and stops sending CAN frames.",
            _inject(FaultType.ECU_OFFLINE, OFFLINE_ECU),
            done=lambda sim: _warning(sim, "CAN_COMM_LOST"),
            hold_s=1.0,
            timeout_s=10.0,
        ),
        DemoStep(
            "ECU timeout reported",
            "No frame for 1.5 s: the watchdog reports the TCM offline and sets DTC U0101.",
            lambda sim: None,
            done=lambda sim: _dtc(sim, "U0101"),
            hold_s=5.0,
            timeout_s=10.0,
        ),
        DemoStep(
            "Communication recovers",
            "The TCM reboots and is back on the bus; the watchdog sees it ONLINE again.",
            _clear(FaultType.ECU_OFFLINE, OFFLINE_ECU),
            done=lambda sim: not _warning(sim, "CAN_COMM_LOST") and not _dtc(sim, "U0101"),
            hold_s=3.0,
            timeout_s=10.0,
        ),
        DemoStep(
            "Fault clears",
            "Cooling system repaired: coolant falls, OVERHEAT and DTC P0217 clear.",
            _clear(FaultType.ENGINE_OVERHEAT),
            done=lambda sim: not _engine(EngineState.OVERHEAT)(sim) and not _dtc(sim, "P0217"),
            hold_s=3.0,
            timeout_s=90.0,
        ),
    ]


class DemoDirector:
    """Plays the demo steps against a simulator; call ``step()`` after each tick."""

    def __init__(self, sim: Simulator, steps: list[DemoStep] | None = None) -> None:
        self.sim = sim
        self.steps = steps if steps is not None else build_steps()
        self.index = -1
        self.finished = False
        self.stopped = False
        self.timed_out: list[str] = []
        self._started_at = sim.time
        self._ended_at: float | None = None
        self._step_at = sim.time
        self._ready_at: float | None = None
        self._injected: set[tuple[FaultType, str | None]] = set()
        self._log("DEMO_START", "Demo Mode started")
        self._advance()

    @property
    def active(self) -> bool:
        return not (self.finished or self.stopped)

    @property
    def current(self) -> DemoStep | None:
        return self.steps[self.index] if 0 <= self.index < len(self.steps) else None

    def step(self) -> None:
        step = self.current
        if not self.active or step is None:
            return
        now = self.sim.time
        if self._ready_at is None and step.done(self.sim):
            self._ready_at = now
        if self._ready_at is not None and now - self._ready_at >= step.hold_s - 1e-9:
            self._advance()
        elif now - self._step_at >= step.timeout_s:
            # Don't hang the demo; record it so tests and the log show what went wrong.
            self.timed_out.append(step.title)
            self._log(
                "DEMO_STEP_TIMEOUT",
                f"Demo step '{step.title}' did not complete in {step.timeout_s:g} s",
                severity="WARNING",
            )
            self._advance()

    def stop(self) -> None:
        """Abort: undo the demo's faults and hand the car back with pedals released."""
        if not self.active:
            return
        self.stopped = True
        self._ended_at = self.sim.time
        for kind, target in self._injected:
            self.sim.faults.clear(kind, target)
        self.sim.driver.throttle = 0.0
        self._log("DEMO_STOPPED", "Demo Mode stopped")

    def status(self) -> dict[str, Any]:
        step = self.current
        return {
            "active": self.active,
            "finished": self.finished,
            "step": self.index + 1,
            "total": len(self.steps),
            "title": step.title if step else None,
            "caption": step.caption if step else None,
            "elapsed_s": round((self._ended_at or self.sim.time) - self._started_at, 1),
        }

    def _advance(self) -> None:
        self.index += 1
        self._step_at = self.sim.time
        self._ready_at = None
        step = self.current
        if step is None:
            self.finished = True
            self._ended_at = self.sim.time
            self.index = len(self.steps) - 1
            self._log("DEMO_COMPLETE", "Demo Mode complete")
            return
        before = set(self.sim.faults.active)
        step.enter(self.sim)
        self._injected |= set(self.sim.faults.active) - before
        self._injected &= set(self.sim.faults.active)
        self._log(
            "DEMO_STEP",
            f"Demo {self.index + 1}/{len(self.steps)}: {step.title}",
            step=self.index + 1,
        )

    def _log(self, event: str, message: str, severity: str = "INFO", **details: Any) -> None:
        self.sim.events.add(event, severity, "DEMO", message, self.sim.time, **details)
