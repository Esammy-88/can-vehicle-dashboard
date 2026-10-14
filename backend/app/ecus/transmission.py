"""Transmission Control Module (6-speed automatic).

Owns the selector (P/R/N/D) with a shift interlock, picks gears from vehicle
speed and driver demand, and broadcasts VEHICLE_STATUS and
TRANSMISSION_STATUS. Throttle and engine speed come from the ECM over CAN.
"""

from __future__ import annotations

import random
from collections.abc import Mapping

import can

from app.can.decoder import CanCodec
from app.can.frames import SignalValue
from app.ecus.base import Ecu
from app.simulation.physics import GEAR_RATIOS, kmh_to_engine_rpm
from app.simulation.sensors import Sensor
from app.simulation.vehicle import DriverInputs, Selector, VehicleModel

TOP_GEAR = len(GEAR_RATIOS)
SHIFT_DURATION_S = 0.4
MIN_SHIFT_INTERVAL_S = 0.8
PARK_REVERSE_MAX_KMH = 3.0  # P and R are refused above this speed
LAUNCH_GEAR_BELOW_KMH = 5.0
REDLINE_UPSHIFT_RPM = 6200.0
HYSTERESIS_RPM = 300.0


def upshift_rpm(throttle: float) -> float:
    """Light throttle shifts early (~2000 rpm), full throttle near redline."""
    return 2000.0 + 40.0 * throttle


def downshift_rpm(throttle: float) -> float:
    """Pressing harder raises the downshift point: this is kickdown."""
    return 1200.0 + 25.0 * throttle


def gear_for_speed(speed_kmh: float, throttle: float) -> int:
    for gear in range(1, TOP_GEAR + 1):
        if kmh_to_engine_rpm(speed_kmh, gear) <= upshift_rpm(throttle):
            return gear
    return TOP_GEAR


class TransmissionEcu(Ecu):
    node = "TCM"

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
        self._speed_sensor = Sensor(lambda: plant.speed_kmh, 0.05, rng, minimum=0.0)
        self._temp_sensor = Sensor(lambda: plant.trans_c, 0.2, rng)

        self.selector = Selector.P
        self.gear = 0  # engaged forward gear in D, 0 otherwise
        self.speed_kmh = 0.0
        self.trans_temp_c = 0.0
        self.shifting = False
        self._shift_until = 0.0
        self._last_shift = float("-inf")

    @property
    def drive_gear(self) -> int | None:
        if self.selector is Selector.D:
            return self.gear
        if self.selector is Selector.R:
            return -1
        return None

    @property
    def park(self) -> bool:
        return self.selector is Selector.P

    def update(self, now: float) -> None:
        self.speed_kmh = self._speed_sensor.read()
        self.trans_temp_c = self._temp_sensor.read()
        engine = self.latest("ENGINE_STATUS", now)
        throttle = float(engine["ThrottlePosition"]) if engine else 0.0
        engine_rpm = float(engine["EngineRPM"]) if engine else 0.0

        self._handle_selector(throttle)
        if self.selector is Selector.D:
            self._auto_shift(now, throttle, engine_rpm)
        self.shifting = now < self._shift_until

    def _handle_selector(self, throttle: float) -> None:
        requested = self.driver.gear_selector
        if requested is self.selector:
            return
        if requested in (Selector.P, Selector.R) and self.speed_kmh > PARK_REVERSE_MAX_KMH:
            return  # mechanical protection: no P/R while moving
        if self.selector is Selector.P and not self.driver.brake_pressed:
            return  # shift lock: brake required to leave Park
        self.selector = requested
        self.gear = gear_for_speed(self.speed_kmh, throttle) if requested is Selector.D else 0

    def _auto_shift(self, now: float, throttle: float, engine_rpm: float) -> None:
        if self.speed_kmh < LAUNCH_GEAR_BELOW_KMH:
            if self.gear != 1:
                self._shift_to(1, now)
            return
        if now < self._shift_until or now - self._last_shift < MIN_SHIFT_INTERVAL_S:
            return

        rpm_here = kmh_to_engine_rpm(self.speed_kmh, self.gear)
        if self.gear < TOP_GEAR and not self.driver.brake_pressed:  # no upshift while braking
            rpm_above = kmh_to_engine_rpm(self.speed_kmh, self.gear + 1)
            wants_up = rpm_here > upshift_rpm(throttle) or engine_rpm > REDLINE_UPSHIFT_RPM
            if wants_up and rpm_above > downshift_rpm(throttle) + HYSTERESIS_RPM:
                self._shift_to(self.gear + 1, now)
                return
        if self.gear > 1:
            rpm_below = kmh_to_engine_rpm(self.speed_kmh, self.gear - 1)
            if (
                rpm_here < downshift_rpm(throttle)
                and rpm_below < upshift_rpm(throttle) - HYSTERESIS_RPM
            ):
                self._shift_to(self.gear - 1, now)

    def _shift_to(self, gear: int, now: float) -> None:
        self.gear = gear
        self._shift_until = now + SHIFT_DURATION_S
        self._last_shift = now

    def signals_for(self, message_name: str) -> Mapping[str, SignalValue]:
        if message_name == "VEHICLE_STATUS":
            return {
                "VehicleSpeed": self.speed_kmh,
                "BrakeSwitch": int(self.driver.brake_pressed),
            }
        return {
            "GearSelector": self.selector.value,
            "CurrentGear": self.gear if self.selector is Selector.D else 0,
            "TransTemp": round(self.trans_temp_c),
            "TransFault": 0,
            "ShiftInProgress": int(self.shifting),
        }
