"""Engine Control Module.

Reads the throttle pedal, crank speed and temperature sensors, runs the engine
state machine, commands fuel and torque limiting, and broadcasts
ENGINE_STATUS and ENGINE_TEMPERATURE. Vehicle speed is not wired to the ECM:
it is received from the TCM over CAN (VEHICLE_STATUS).
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from enum import StrEnum

import can

from app.can.decoder import CanCodec
from app.can.frames import SignalValue
from app.ecus.base import Ecu
from app.simulation.physics import first_order
from app.simulation.sensors import Sensor
from app.simulation.vehicle import DriverInputs, VehicleModel


class EngineState(StrEnum):
    OFF = "OFF"
    STARTING = "STARTING"
    IDLE = "IDLE"
    ACCELERATING = "ACCELERATING"
    CRUISING = "CRUISING"
    DECELERATING = "DECELERATING"
    OVERHEAT = "OVERHEAT"
    FAULT = "FAULT"


RUNNING_RPM = 700.0
STALL_RPM = 300.0
START_TIMEOUT_S = 3.0
OVERHEAT_ENTER_C = 112.0
OVERHEAT_EXIT_C = 105.0
LIMP_TORQUE_LIMIT = 0.5
TREND_TAU_S = 0.5  # smoothing of acceleration / rpm-rate estimates


class EngineEcu(Ecu):
    node = "ECM"

    def __init__(
        self,
        bus: can.BusABC,
        codec: CanCodec,
        plant: VehicleModel,
        driver: DriverInputs,
        rng: random.Random,
    ) -> None:
        super().__init__(bus, codec)
        self.driver = driver
        self._rpm_sensor = Sensor(lambda: plant.engine_rpm, 3.0, rng, minimum=0.0, zero_below=1.0)
        self._load_sensor = Sensor(lambda: plant.engine_load * 100.0, 0.3, rng, 0.0, 100.0)
        self._coolant_sensor = Sensor(lambda: plant.coolant_c, 0.2, rng)
        self._oil_sensor = Sensor(lambda: plant.oil_c, 0.2, rng)

        self.state = EngineState.OFF
        self.fuel_enabled = False
        self.torque_limit = 1.0
        self.rpm = self.load = 0.0
        self.coolant_c = self.oil_c = 0.0
        self.vehicle_speed_kmh = 0.0
        self.accel_kmh_s = 0.0
        self.rpm_rate = 0.0
        self._start_at = 0.0
        self._last_time: float | None = None

    def update(self, now: float) -> None:
        prev_rpm, prev_speed = self.rpm, self.vehicle_speed_kmh
        self.rpm = self._rpm_sensor.read()
        # Load is derived from airflow; a stopped engine has none, so no sensor noise either.
        self.load = self._load_sensor.read() if self.rpm > STALL_RPM else 0.0
        self.coolant_c = self._coolant_sensor.read()
        self.oil_c = self._oil_sensor.read()
        vehicle = self.latest("VEHICLE_STATUS", now)
        self.vehicle_speed_kmh = float(vehicle["VehicleSpeed"]) if vehicle else 0.0

        if self._last_time is not None and now > self._last_time:
            dt = now - self._last_time
            accel = (self.vehicle_speed_kmh - prev_speed) / dt
            rpm_rate = (self.rpm - prev_rpm) / dt
            self.accel_kmh_s = first_order(self.accel_kmh_s, accel, TREND_TAU_S, dt)
            self.rpm_rate = first_order(self.rpm_rate, rpm_rate, TREND_TAU_S, dt)
        self._last_time = now

        self.state = self._next_state(now)
        self.fuel_enabled = self.state not in (EngineState.OFF, EngineState.FAULT)
        self.torque_limit = LIMP_TORQUE_LIMIT if self.state is EngineState.OVERHEAT else 1.0

    def _next_state(self, now: float) -> EngineState:
        s = self.state
        if not self.driver.ignition:
            return EngineState.OFF
        if s is EngineState.OFF:
            self._start_at = now
            return EngineState.STARTING
        if s is EngineState.FAULT:
            return s  # latched until the ignition is cycled
        if s is EngineState.STARTING:
            if self.rpm >= RUNNING_RPM:
                return EngineState.IDLE
            return EngineState.FAULT if now - self._start_at > START_TIMEOUT_S else s

        if self.rpm < STALL_RPM:
            return EngineState.FAULT  # stalled, e.g. out of fuel
        if s is EngineState.OVERHEAT:
            return s if self.coolant_c > OVERHEAT_EXIT_C else self._driving_state()
        if self.coolant_c >= OVERHEAT_ENTER_C:
            return EngineState.OVERHEAT
        return self._driving_state()

    def _driving_state(self) -> EngineState:
        throttle = self.driver.throttle
        if self.accel_kmh_s > 1.5 or (throttle > 5.0 and self.rpm_rate > 300.0):
            return EngineState.ACCELERATING
        coasting = throttle < 2.0 and self.vehicle_speed_kmh > 2.0 and self.accel_kmh_s < 0.0
        if self.accel_kmh_s < -1.5 or coasting:
            return EngineState.DECELERATING
        if self.vehicle_speed_kmh < 1.0:
            return EngineState.IDLE
        return EngineState.CRUISING

    def signals_for(self, message_name: str) -> Mapping[str, SignalValue]:
        if message_name == "ENGINE_STATUS":
            return {
                "EngineRPM": self.rpm,
                "EngineLoad": self.load,
                "ThrottlePosition": self.driver.throttle,
                "EngineRunning": int(self.rpm > STALL_RPM and self.fuel_enabled),
                "EngineState": self.state.value,
            }
        return {"CoolantTemp": round(self.coolant_c), "OilTemp": round(self.oil_c)}
