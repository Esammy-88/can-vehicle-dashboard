"""Instrument Panel Cluster (dashboard ECU).

Like a real cluster, the IPC has no sensors of its own: everything it shows
is decoded from CAN. It evaluates warning conditions, integrates its own
odometer from received vehicle speed, broadcasts DASHBOARD_STATUS (warning
lamps + master severity) and exposes a view the web dashboard renders.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

import can

from app.can.decoder import CanCodec
from app.can.frames import SignalValue
from app.ecus.base import Ecu

STARTUP_GRACE_S = 1.0  # don't report lost communication before anything had a chance to send
LOW_FUEL_PCT = 15.0
OVERHEAT_C = 110.0
HIGH_OIL_C = 130.0
HIGH_RPM = 6500.0
DOOR_MOVING_KMH = 5.0
SEATBELT_MOVING_KMH = 10.0

# Which ECU each cluster input comes from, for "CAN COMMUNICATION LOST" reporting.
SOURCES: dict[str, tuple[str, ...]] = {
    "ECM": ("ENGINE_STATUS", "ENGINE_TEMPERATURE"),
    "TCM": ("VEHICLE_STATUS", "TRANSMISSION_STATUS"),
    "BCM": ("BODY_STATUS",),
}
ECU_NAMES = {"ECM": "Engine ECU", "TCM": "Transmission ECU", "BCM": "Body ECU"}


class Severity(IntEnum):
    NONE = 0
    INFO = 1
    WARNING = 2
    CRITICAL = 3


@dataclass(frozen=True)
class ClusterWarning:
    code: str
    severity: Severity
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "severity": self.severity.name, "message": self.message}


# Warning code -> DASHBOARD_STATUS lamp signal
LAMPS = {
    "LOW_FUEL": "WarnLowFuel",
    "ENGINE_OVERHEAT": "WarnEngineOverheat",
    "HIGH_OIL_TEMP": "WarnHighOilTemp",
    "CAN_COMM_LOST": "WarnCanCommLost",
    "ENGINE_FAULT": "WarnEngineFault",
    "TRANSMISSION_FAULT": "WarnTransFault",
    "DOOR_OPEN": "WarnDoorOpen",
    "SEATBELT": "WarnSeatbelt",
}


class DashboardEcu(Ecu):
    node = "IPC"

    def __init__(self, bus: can.BusABC, codec: CanCodec) -> None:
        super().__init__(bus, codec)
        self.odometer_km = 0.0
        self.warnings: list[ClusterWarning] = []
        self.sources_online: dict[str, bool] = dict.fromkeys(SOURCES, False)
        self._data: dict[str, dict[str, SignalValue] | None] = {}
        self._last_time: float | None = None

    @property
    def master_severity(self) -> Severity:
        return max((w.severity for w in self.warnings), default=Severity.NONE)

    def update(self, now: float) -> None:
        self._data = {name: self.latest(name, now) for names in SOURCES.values() for name in names}
        self.sources_online = {
            ecu: all(self._data[name] is not None for name in names)
            for ecu, names in SOURCES.items()
        }

        vehicle = self._data["VEHICLE_STATUS"]
        if vehicle is not None and self._last_time is not None:
            self.odometer_km += float(vehicle["VehicleSpeed"]) * (now - self._last_time) / 3600.0
        self._last_time = now

        self.warnings = self._evaluate_warnings(now)

    def _evaluate_warnings(self, now: float) -> list[ClusterWarning]:
        engine = self._data["ENGINE_STATUS"] or {}
        temps = self._data["ENGINE_TEMPERATURE"] or {}
        vehicle = self._data["VEHICLE_STATUS"] or {}
        trans = self._data["TRANSMISSION_STATUS"] or {}
        body = self._data["BODY_STATUS"] or {}
        speed = float(vehicle.get("VehicleSpeed", 0.0))
        out: list[ClusterWarning] = []

        if now > STARTUP_GRACE_S:
            for ecu, online in self.sources_online.items():
                if not online:
                    out.append(
                        ClusterWarning(
                            "CAN_COMM_LOST",
                            Severity.CRITICAL,
                            f"{ECU_NAMES[ecu]} offline: CAN communication lost",
                        )
                    )

        if engine.get("EngineState") == "FAULT":
            out.append(ClusterWarning("ENGINE_FAULT", Severity.CRITICAL, "Engine fault"))
        elif temps.get("EngineDtcCount", 0) > 0:
            count = temps["EngineDtcCount"]
            out.append(
                ClusterWarning(
                    "CHECK_ENGINE",
                    Severity.WARNING,
                    f"Check engine: {count} fault code{'s' if count > 1 else ''} active",
                )
            )
        if engine.get("EngineRPM", 0) > HIGH_RPM:
            out.append(ClusterWarning("HIGH_RPM", Severity.WARNING, "Engine speed too high"))
        if engine.get("EngineState") == "OVERHEAT" or temps.get("CoolantTemp", 0) >= OVERHEAT_C:
            out.append(ClusterWarning("ENGINE_OVERHEAT", Severity.CRITICAL, "Engine overheat"))
        if temps.get("OilTemp", 0) >= HIGH_OIL_C:
            out.append(ClusterWarning("HIGH_OIL_TEMP", Severity.WARNING, "High oil temperature"))
        if trans.get("TransFault") == 1:
            out.append(
                ClusterWarning("TRANSMISSION_FAULT", Severity.CRITICAL, "Transmission fault")
            )
        if body and body["FuelLevel"] < LOW_FUEL_PCT:
            out.append(ClusterWarning("LOW_FUEL", Severity.WARNING, "Low fuel"))

        open_doors = [
            label
            for label, sig in (
                ("front left", "DoorFrontLeftOpen"),
                ("front right", "DoorFrontRightOpen"),
                ("rear left", "DoorRearLeftOpen"),
                ("rear right", "DoorRearRightOpen"),
            )
            if body.get(sig) == 1
        ]
        if open_doors:
            severity = Severity.WARNING if speed > DOOR_MOVING_KMH else Severity.INFO
            out.append(ClusterWarning("DOOR_OPEN", severity, "Door open: " + ", ".join(open_doors)))

        if body.get("SeatbeltFastened") == 0 and engine.get("EngineRunning") == 1:
            severity = Severity.WARNING if speed > SEATBELT_MOVING_KMH else Severity.INFO
            out.append(ClusterWarning("SEATBELT", severity, "Fasten seatbelt"))

        return sorted(out, key=lambda w: -w.severity)

    def signals_for(self, message_name: str) -> Mapping[str, SignalValue]:
        active = {w.code for w in self.warnings}
        lamps = {signal: int(code in active) for code, signal in LAMPS.items()}
        lamps["WarnEngineFault"] |= int("CHECK_ENGINE" in active)  # same MIL lamp
        return {
            **lamps,
            "MasterSeverity": self.master_severity.name,
            "Odometer": self.odometer_km,
        }

    def view(self) -> dict[str, Any]:
        """Everything the instrument cluster displays; None where data is missing."""
        engine = self._data.get("ENGINE_STATUS") or {}
        temps = self._data.get("ENGINE_TEMPERATURE") or {}
        vehicle = self._data.get("VEHICLE_STATUS") or {}
        trans = self._data.get("TRANSMISSION_STATUS") or {}
        body = self._data.get("BODY_STATUS") or {}

        selector = trans.get("GearSelector")
        gear = trans.get("CurrentGear")
        gear_display = f"D{gear}" if selector == "D" and gear else selector

        return {
            "speed_kmh": vehicle.get("VehicleSpeed"),
            "brake": _bool(vehicle.get("BrakeSwitch")),
            "rpm": engine.get("EngineRPM"),
            "engine_load": engine.get("EngineLoad"),
            "throttle": engine.get("ThrottlePosition"),
            "engine_running": _bool(engine.get("EngineRunning")),
            "engine_state": engine.get("EngineState"),
            "coolant_c": temps.get("CoolantTemp"),
            "oil_c": temps.get("OilTemp"),
            "gear": gear_display,
            "selector": selector,
            "current_gear": gear,
            "trans_c": trans.get("TransTemp"),
            "shift_in_progress": _bool(trans.get("ShiftInProgress")),
            "fuel_pct": body.get("FuelLevel"),
            "headlights": body.get("Headlights"),
            "turn_indicator": body.get("TurnIndicator"),
            "brake_lights": _bool(body.get("BrakeLights")),
            "seatbelt_fastened": _bool(body.get("SeatbeltFastened")),
            "doors_open": {
                "front_left": _bool(body.get("DoorFrontLeftOpen")),
                "front_right": _bool(body.get("DoorFrontRightOpen")),
                "rear_left": _bool(body.get("DoorRearLeftOpen")),
                "rear_right": _bool(body.get("DoorRearRightOpen")),
            },
            "odometer_km": round(self.odometer_km, 2),
            "warnings": [w.to_dict() for w in self.warnings],
            "master_severity": self.master_severity.name,
            "sources_online": dict(self.sources_online),
        }


def _bool(value: SignalValue | None) -> bool | None:
    return None if value is None else bool(value)
