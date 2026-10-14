"""Software-in-the-loop orchestrator: plant + ECUs on a shared CAN bus.

Each tick: every ECU receives, runs its logic and transmits whatever is due;
then the plant integrates one step using the ECUs' actuator commands. Time is
simulated (tick count x TICK_S), so the same inputs always give the same run.
A real-time driver only has to call ``step()`` every TICK_S of wall time.
"""

from __future__ import annotations

import logging
import random
from types import TracebackType

from app.can.bus import BusFactory
from app.can.decoder import CanCodec
from app.ecus.base import Ecu
from app.ecus.body import BodyEcu
from app.ecus.engine import EngineEcu
from app.ecus.transmission import TransmissionEcu
from app.simulation.vehicle import Actuators, DriverInputs, VehicleModel

log = logging.getLogger(__name__)

TICK_S = 0.01


class Simulator:
    def __init__(self, factory: BusFactory, codec: CanCodec, seed: int = 0) -> None:
        rng = random.Random(seed)
        self.driver = DriverInputs()
        self.vehicle = VehicleModel()
        self.engine = EngineEcu(factory.open(), codec, self.vehicle, self.driver, rng)
        self.transmission = TransmissionEcu(factory.open(), codec, self.vehicle, self.driver, rng)
        self.body = BodyEcu(factory.open(), codec, self.vehicle, self.driver, rng)
        self.ecus: list[Ecu] = [self.engine, self.transmission, self.body]
        self.crashed: set[str] = set()
        self._ticks = 0

    @property
    def time(self) -> float:
        return self._ticks * TICK_S

    def step(self) -> None:
        self._ticks += 1
        for ecu in self.ecus:
            if ecu.node in self.crashed:
                continue
            try:
                ecu.step(self.time)
            except Exception:
                # One failing ECU must not take the network down with it.
                log.exception("ECU %s crashed; taking it off the bus", ecu.node)
                self.crashed.add(ecu.node)
                ecu.shutdown()
        self.vehicle.step(TICK_S, self.actuators(), self.driver)

    def run_for(self, seconds: float) -> None:
        for _ in range(round(seconds / TICK_S)):
            self.step()

    def actuators(self) -> Actuators:
        act = Actuators()
        if self.engine.node not in self.crashed:
            act.fuel_enabled = self.engine.fuel_enabled
            act.torque_limit = self.engine.torque_limit
        if self.transmission.node in self.crashed:
            act.park = False  # a dead TCM leaves the gearbox in neutral
        else:
            act.drive_gear = self.transmission.drive_gear
            act.park = self.transmission.park
            act.shifting = self.transmission.shifting
        return act

    def close(self) -> None:
        for ecu in self.ecus:
            if ecu.node not in self.crashed:
                ecu.shutdown()

    def __enter__(self) -> Simulator:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
