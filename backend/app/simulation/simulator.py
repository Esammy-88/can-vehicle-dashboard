"""Software-in-the-loop orchestrator: plant + ECUs on a shared CAN bus.

Each tick: injected faults act, every ECU receives, runs its logic and
transmits whatever is due, the plant integrates one step using the ECUs'
actuator commands, and passive observers (bus monitor, graph history, event
log) record what happened. Time is simulated (tick count x TICK_S), so the
same inputs always give the same run. A real-time driver only has to call
``step()`` every TICK_S of wall time.
"""

from __future__ import annotations

import logging
import random
from types import TracebackType

from app.can.bus import BusFactory
from app.can.decoder import CanCodec
from app.ecus.base import Ecu
from app.ecus.body import BodyEcu
from app.ecus.dashboard import DashboardEcu, Severity
from app.ecus.diagnostics import DiagnosticEcu, DtcEvent
from app.ecus.engine import EngineEcu, EngineState
from app.ecus.transmission import TransmissionEcu
from app.monitoring.bus_monitor import BusMonitor
from app.monitoring.event_log import EventLog
from app.monitoring.history import TelemetryHistory
from app.simulation.faults import FaultManager
from app.simulation.vehicle import Actuators, DriverInputs, VehicleModel

log = logging.getLogger(__name__)

TICK_S = 0.01
INVALID_FRAME_LOG_INTERVAL_S = 10.0  # first bad frame is logged at once, then a summary
# Transitions between these driving states happen constantly; they are not logged.
_DRIVING_STATES = {EngineState.ACCELERATING, EngineState.CRUISING, EngineState.DECELERATING}


class Simulator:
    def __init__(
        self,
        factory: BusFactory,
        codec: CanCodec,
        seed: int = 0,
        events: EventLog | None = None,
    ) -> None:
        rng = random.Random(seed)
        self.codec = codec
        self.events = events if events is not None else EventLog()
        self.driver = DriverInputs()
        self.vehicle = VehicleModel()
        self.engine = EngineEcu(factory.open(), codec, self.vehicle, self.driver, rng)
        self.transmission = TransmissionEcu(factory.open(), codec, self.vehicle, self.driver, rng)
        self.body = BodyEcu(factory.open(), codec, self.vehicle, self.driver, rng)
        # The cluster and diagnostics step last so they see this tick's frames.
        self.dashboard = DashboardEcu(factory.open(), codec)
        self.diagnostics = DiagnosticEcu(factory.open(), codec)
        self.ecus: list[Ecu] = [
            self.engine,
            self.transmission,
            self.body,
            self.dashboard,
            self.diagnostics,
        ]
        self.crashed: set[str] = set()  # software failure: isolated for good
        self.disabled: set[str] = set()  # powered off by fault injection
        self.bus_down = False
        self.faults = FaultManager(self, factory)
        # Passive observers: a bus tap for the CAN monitor, and graph history.
        self.monitor = BusMonitor(factory.open(), codec)
        self.history = TelemetryHistory()
        self._ticks = 0
        self._last_engine_state = self.engine.state
        self._last_selector = self.transmission.selector
        self._last_warnings: dict[str, Severity] = {}
        self._logged_errors = 0
        self._next_error_log = 0.0

    @property
    def time(self) -> float:
        return self._ticks * TICK_S

    def ecu(self, node: str) -> Ecu:
        return next(e for e in self.ecus if e.node == node)

    def is_offline(self, node: str) -> bool:
        return node in self.crashed or node in self.disabled

    def step(self) -> None:
        self._ticks += 1
        now = self.time
        self.faults.step(now)
        for ecu in self.ecus:
            if self.is_offline(ecu.node):
                continue
            ecu.tx_enabled = not self.bus_down
            try:
                ecu.step(now)
            except Exception:
                # One failing ECU must not take the network down with it.
                log.exception("ECU %s crashed; taking it off the bus", ecu.node)
                self.crashed.add(ecu.node)
                ecu.shutdown()
                self.events.add(
                    "ECU_CRASH", "CRITICAL", ecu.node, f"{ecu.node} software crash", now
                )
        self.vehicle.step(TICK_S, self.actuators(), self.driver)
        self.monitor.poll(now)
        if self.history.due(now):
            self.history.sample(now, self.dashboard.view(), self.monitor.message_rate())
        self._observe(now)

    def run_for(self, seconds: float) -> None:
        for _ in range(round(seconds / TICK_S)):
            self.step()

    def actuators(self) -> Actuators:
        act = Actuators()
        if not self.is_offline(self.engine.node):
            act.fuel_enabled = self.engine.fuel_enabled
            act.throttle = self.engine.throttle_cmd
            act.torque_limit = self.engine.torque_limit
        if self.is_offline(self.transmission.node):
            act.park = False  # a dead TCM leaves the gearbox in neutral
        else:
            act.drive_gear = self.transmission.drive_gear
            act.park = self.transmission.park
            act.shifting = self.transmission.shifting
        return act

    def _observe(self, now: float) -> None:
        """Turn changes in state into event-log entries."""
        state = self.engine.state
        if state is not self._last_engine_state and not (
            state in _DRIVING_STATES and self._last_engine_state in _DRIVING_STATES
        ):
            critical = state in (EngineState.OVERHEAT, EngineState.FAULT)
            self.events.add(
                "ENGINE_STATE",
                "CRITICAL" if critical else "INFO",
                "ECM",
                f"Engine {self._last_engine_state.value} → {state.value}",
                now,
                previous=self._last_engine_state.value,
                state=state.value,
            )
        self._last_engine_state = state

        selector = self.transmission.selector
        if selector is not self._last_selector:
            self.events.add(
                "GEAR_SELECTOR",
                "INFO",
                "TCM",
                f"Selector {self._last_selector.value} → {selector.value}",
                now,
            )
            self._last_selector = selector

        current = {w.code: w for w in self.dashboard.warnings}
        for code, w in current.items():
            if self._last_warnings.get(code) != w.severity:
                self.events.add(
                    w.code, w.severity.name, "IPC", f"Warning: {w.message}", now, raised=True
                )
        for code in self._last_warnings.keys() - current.keys():
            self.events.add(code, "INFO", "IPC", f"Warning cleared: {code}", now, raised=False)
        self._last_warnings = {code: w.severity for code, w in current.items()}

        for event in self.diagnostics.events:
            if isinstance(event, DtcEvent):
                r = event.record
                set_ = event.event == "DTC_SET"
                description = r.to_dict()["description"]
                self.events.add(
                    event.event,
                    ("CRITICAL" if r.code.startswith("U") else "WARNING") if set_ else "INFO",
                    r.ecu,
                    f"{'DTC set' if set_ else 'DTC cleared'}: {r.code} {description}",
                    now,
                    code=r.code,
                )
            elif event.event == "ECU_TIMEOUT":
                self.events.add(
                    "ECU_TIMEOUT",
                    "CRITICAL",
                    event.node,
                    f"{event.name.upper()} OFFLINE: no frame for {event.timeout_s:g} s "
                    f"(last message {event.last_message})",
                    now,
                    **event.details(),
                )
            else:
                self.events.add(
                    "ECU_ONLINE", "INFO", event.node, f"{event.name.upper()} ONLINE", now
                )
        self.diagnostics.events.clear()

        for edge in self.monitor.edges:
            timeout = edge["event"] == "MESSAGE_TIMEOUT"
            self.events.add(
                edge["event"],
                "WARNING" if timeout else "INFO",
                edge["sender"],
                f"{edge['name']} (0x{edge['id']:03X}) {'timed out' if timeout else 'restored'}",
                now,
                can_id=edge["id"],
            )
        self.monitor.edges.clear()

        errors = sum(self.monitor.errors_by_type.values())
        if errors > self._logged_errors and now >= self._next_error_log:
            new = errors - self._logged_errors
            self.events.add(
                "INVALID_FRAMES",
                "WARNING",
                "BUS",
                f"{new} invalid CAN frame{'s' if new > 1 else ''} received",
                now,
                by_type=dict(self.monitor.errors_by_type),
            )
            self._logged_errors = errors
            self._next_error_log = now + INVALID_FRAME_LOG_INTERVAL_S

    def close(self) -> None:
        self.faults.close()
        for ecu in self.ecus:
            if ecu.node not in self.crashed:
                ecu.shutdown()
        self.monitor.bus.shutdown()

    def __enter__(self) -> Simulator:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
