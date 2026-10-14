"""Body Control Module.

Reads the driver's switches (lights, doors, seatbelt, indicators, brake pedal
switch) and the fuel level sender, drives the brake lights and broadcasts
BODY_STATUS.
"""

from __future__ import annotations

import random
from collections.abc import Mapping

import can

from app.can.decoder import CanCodec
from app.can.frames import SignalValue
from app.ecus.base import Ecu
from app.simulation.physics import first_order
from app.simulation.sensors import Sensor
from app.simulation.vehicle import DriverInputs, VehicleModel

FUEL_GAUGE_TAU_S = 2.0  # damping so fuel slosh does not make the gauge jitter


class BodyEcu(Ecu):
    node = "BCM"

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
        self._fuel_sensor = Sensor(lambda: plant.fuel_pct, 1.0, rng, 0.0, 100.0)
        self.fuel_pct: float | None = None
        self.brake_lights = False
        self._last_time = 0.0

    def update(self, now: float) -> None:
        reading = self._fuel_sensor.read()
        if self.fuel_pct is None:
            self.fuel_pct = reading
        else:
            self.fuel_pct = first_order(
                self.fuel_pct, reading, FUEL_GAUGE_TAU_S, now - self._last_time
            )
        self._last_time = now
        self.brake_lights = self.driver.brake_pressed

    def signals_for(self, message_name: str) -> Mapping[str, SignalValue]:
        doors = self.driver.doors_open
        return {
            "FuelLevel": self.fuel_pct or 0.0,
            "Headlights": self.driver.headlights.value,
            "TurnIndicator": self.driver.turn_indicator.value,
            "DoorFrontLeftOpen": int(doors["front_left"]),
            "DoorFrontRightOpen": int(doors["front_right"]),
            "DoorRearLeftOpen": int(doors["rear_left"]),
            "DoorRearRightOpen": int(doors["rear_right"]),
            "SeatbeltFastened": int(self.driver.seatbelt_fastened),
            "BrakeLights": int(self.brake_lights),
        }
