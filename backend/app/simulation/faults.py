"""Fault injection.

Each fault is injected where it would physically happen, so detection has to
work the way it would in a real car: the plant (cooling failure, fuel leak,
engine runaway), a sensor (open circuit, stuck pedal), an ECU (powered off,
one message no longer sent) or the bus itself (rogue node, wiring fault).
Clearing a fault undoes exactly what injecting it did.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import can

from app.can.bus import BusFactory

if TYPE_CHECKING:
    from app.simulation.simulator import Simulator


class FaultType(StrEnum):
    ENGINE_OVERHEAT = "ENGINE_OVERHEAT"
    LOW_FUEL = "LOW_FUEL"
    SENSOR_FAILURE = "SENSOR_FAILURE"
    ECU_OFFLINE = "ECU_OFFLINE"
    CAN_TIMEOUT = "CAN_TIMEOUT"
    TRANSMISSION_OVERHEAT = "TRANSMISSION_OVERHEAT"
    STUCK_THROTTLE = "STUCK_THROTTLE"
    INVALID_CAN = "INVALID_CAN"
    BUS_INTERRUPTION = "BUS_INTERRUPTION"
    HIGH_RPM = "HIGH_RPM"


@dataclass(frozen=True)
class FaultSpec:
    label: str
    description: str
    targets: tuple[str, ...] = ()  # choices, for faults that apply to one ECU / message


OFFLINE_TARGETS = ("ECM", "TCM", "BCM")
TIMEOUT_TARGETS = (  # first is the default: the ECM keeps sending ENGINE_STATUS
    "ENGINE_TEMPERATURE",
    "ENGINE_STATUS",
    "VEHICLE_STATUS",
    "TRANSMISSION_STATUS",
    "BODY_STATUS",
)

CATALOG: dict[FaultType, FaultSpec] = {
    FaultType.ENGINE_OVERHEAT: FaultSpec(
        "Engine overheat", "Cooling system failure: coolant climbs past the overheat point"
    ),
    FaultType.LOW_FUEL: FaultSpec("Low fuel", "Fuel leak drains the tank at about 2 % per second"),
    FaultType.SENSOR_FAILURE: FaultSpec(
        "Sensor failure", "Coolant temperature sensor open circuit: reads -40 °C"
    ),
    FaultType.ECU_OFFLINE: FaultSpec(
        "ECU offline", "The ECU powers down and stops communicating", OFFLINE_TARGETS
    ),
    FaultType.CAN_TIMEOUT: FaultSpec(
        "CAN message timeout", "One message stops being sent; its ECU stays alive", TIMEOUT_TARGETS
    ),
    FaultType.TRANSMISSION_OVERHEAT: FaultSpec(
        "Transmission overheat", "Transmission oil cooler failure"
    ),
    FaultType.STUCK_THROTTLE: FaultSpec(
        "Stuck throttle", "Accelerator pedal sensor stuck open (at least 40 %)"
    ),
    FaultType.INVALID_CAN: FaultSpec(
        "Invalid CAN messages", "A rogue node sends corrupted, wrong-length and unknown frames"
    ),
    FaultType.BUS_INTERRUPTION: FaultSpec(
        "CAN bus interruption", "Wiring fault: no frame reaches any node"
    ),
    FaultType.HIGH_RPM: FaultSpec("High RPM", "The engine runs away past the rev limiter"),
}

FUEL_LEAK_LPS = 1.0  # 2 % of the 50 l tank per second
STUCK_PEDAL_MIN_PCT = 40.0
OPEN_CIRCUIT_C = -40.0  # NTC thermistor with a broken wire reads coldest
ROGUE_PERIOD_S = 0.1  # 10 bad frames per second


class FaultError(ValueError):
    pass


@dataclass
class ActiveFault:
    type: FaultType
    target: str | None
    since: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "target": self.target,
            "label": CATALOG[self.type].label,
            "since": round(self.since, 2),
        }


class FaultManager:
    def __init__(self, sim: Simulator, factory: BusFactory) -> None:
        self._sim = sim
        self._factory = factory
        self.active: dict[tuple[FaultType, str | None], ActiveFault] = {}
        self._rogue: can.BusABC | None = None
        self._rogue_next = 0.0
        self._rogue_index = 0

    def inject(self, kind: FaultType, target: str | None = None) -> ActiveFault:
        spec = CATALOG[kind]
        if spec.targets and target not in spec.targets:
            raise FaultError(f"{kind} needs a target, one of {', '.join(spec.targets)}")
        if not spec.targets:
            target = None
        key = (kind, target)
        if key in self.active:
            return self.active[key]
        self._apply(kind, target, on=True)
        fault = self.active[key] = ActiveFault(kind, target, self._sim.time)
        where = f" ({target})" if target else ""
        self._sim.events.add(
            "FAULT_INJECTED",
            "WARNING",
            "FAULTS",
            f"Fault injected: {spec.label}{where}",
            self._sim.time,
            fault=kind.value,
            target=target,
        )
        return fault

    def clear(self, kind: FaultType, target: str | None = None) -> bool:
        fault = self.active.pop((kind, target), None)
        if fault is None:
            return False
        self._apply(kind, target, on=False)
        where = f" ({target})" if target else ""
        self._sim.events.add(
            "FAULT_CLEARED",
            "INFO",
            "FAULTS",
            f"Fault cleared: {CATALOG[kind].label}{where}",
            self._sim.time,
            fault=kind.value,
            target=target,
        )
        return True

    def clear_all(self) -> int:
        keys = list(self.active)
        for kind, target in keys:
            self.clear(kind, target)
        return len(keys)

    def to_list(self) -> list[dict[str, Any]]:
        return [f.to_dict() for f in self.active.values()]

    def _apply(self, kind: FaultType, target: str | None, on: bool) -> None:
        sim = self._sim
        match kind:
            case FaultType.ENGINE_OVERHEAT:
                sim.vehicle.cooling_failure = on
            case FaultType.TRANSMISSION_OVERHEAT:
                sim.vehicle.trans_cooling_failure = on
            case FaultType.LOW_FUEL:
                sim.vehicle.fuel_leak_lps = FUEL_LEAK_LPS if on else 0.0
            case FaultType.HIGH_RPM:
                sim.vehicle.overspeed = on
            case FaultType.SENSOR_FAILURE:
                sim.engine.coolant_sensor.fault_value = OPEN_CIRCUIT_C if on else None
            case FaultType.STUCK_THROTTLE:
                stuck = max(sim.driver.throttle, STUCK_PEDAL_MIN_PCT)
                sim.engine.pedal_sensor.fault_value = stuck if on else None
            case FaultType.ECU_OFFLINE:
                assert target is not None
                if on:
                    sim.disabled.add(target)
                else:
                    sim.disabled.discard(target)
                    sim.ecu(target).reboot()
            case FaultType.CAN_TIMEOUT:
                assert target is not None
                sender = sim.ecu(sim.codec.message(target).senders[0])
                if on:
                    sender.suppressed.add(target)
                else:
                    sender.suppressed.discard(target)
            case FaultType.BUS_INTERRUPTION:
                sim.bus_down = on
            case FaultType.INVALID_CAN:
                if on:
                    self._rogue = self._factory.open()
                    self._rogue_next = sim.time
                elif self._rogue is not None:
                    self._rogue.shutdown()
                    self._rogue = None

    def step(self, now: float) -> None:
        if self._rogue is None or self._sim.bus_down or now + 1e-9 < self._rogue_next:
            return
        self._rogue_next = now + ROGUE_PERIOD_S
        self._rogue.send(self._bad_frame())
        self._rogue_index += 1

    def _bad_frame(self) -> can.Message:
        """Cycle through the three kinds of invalid traffic."""
        kind = self._rogue_index % 3
        if kind == 0:  # valid-looking ENGINE_STATUS with a corrupted payload byte
            frame = self._sim.codec.encode(
                "ENGINE_STATUS",
                {
                    "EngineRPM": 3000,
                    "EngineLoad": 50,
                    "ThrottlePosition": 50,
                    "EngineRunning": 1,
                    "EngineState": "CRUISING",
                },
                counter=self._rogue_index,
            )
            frame.data[1] ^= 0x5A
            return frame
        if kind == 1:  # VEHICLE_STATUS truncated to 4 bytes
            return can.Message(arbitration_id=0x200, data=bytes(4), is_extended_id=False)
        return can.Message(arbitration_id=0x6A5, data=bytes(range(8)), is_extended_id=False)

    def close(self) -> None:
        if self._rogue is not None:
            self._rogue.shutdown()
            self._rogue = None
