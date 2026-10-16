"""The physical vehicle (the "plant") and the driver's controls.

The plant holds physical truth: speed, engine speed, temperatures, fuel. It
knows nothing about CAN. ECUs observe it through sensors and influence it
only through actuator commands (fuel enable, torque limit, engaged gear).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.simulation import physics as p


class Selector(StrEnum):
    P = "P"
    R = "R"
    N = "N"
    D = "D"


class Headlights(StrEnum):
    OFF = "OFF"
    LOW = "LOW"
    HIGH = "HIGH"


class TurnIndicator(StrEnum):
    OFF = "OFF"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    HAZARD = "HAZARD"


DOORS = ("front_left", "front_right", "rear_left", "rear_right")


@dataclass
class DriverInputs:
    """Everything the driver can touch. Pedals are 0-100 %."""

    ignition: bool = False
    throttle: float = 0.0
    brake: float = 0.0
    gear_selector: Selector = Selector.P
    headlights: Headlights = Headlights.OFF
    turn_indicator: TurnIndicator = TurnIndicator.OFF
    doors_open: dict[str, bool] = field(default_factory=lambda: dict.fromkeys(DOORS, False))
    seatbelt_fastened: bool = True

    @property
    def brake_pressed(self) -> bool:
        return self.brake > 2.0


@dataclass
class Actuators:
    """Commands from the ECUs to the plant."""

    fuel_enabled: bool = False  # ECM: injection + ignition
    throttle: float = 0.0  # ECM: commanded throttle 0-100 % (drive-by-wire)
    torque_limit: float = 1.0  # ECM: 0-1, <1 in limp mode
    drive_gear: int | None = None  # TCM: 1-6, -1 reverse, None = no drive (P/N)
    park: bool = True  # TCM: parking pawl engaged
    shifting: bool = False  # TCM: shift in progress, torque briefly reduced


FUEL_TANK_L = 50.0
# Consumption is sped up so the fuel gauge visibly moves during a short demo.
FUEL_CONSUMPTION_SCALE = 10.0
OVERSPEED_RPM = 7200.0


@dataclass
class VehicleModel:
    speed_ms: float = 0.0  # signed; negative when reversing
    engine_rpm: float = 0.0
    engine_torque_nm: float = 0.0
    engine_load: float = 0.0  # 0-1, delivered / available torque
    coolant_c: float = p.AMBIENT_C
    oil_c: float = p.AMBIENT_C
    trans_c: float = p.AMBIENT_C
    fuel_l: float = FUEL_TANK_L * 0.75
    odometer_km: float = 0.0
    engine_running: bool = False

    # Physical faults, set by the fault injection system.
    cooling_failure: bool = False  # engine radiator / water pump failure
    trans_cooling_failure: bool = False  # transmission oil cooler failure
    fuel_leak_lps: float = 0.0
    overspeed: bool = False  # engine runs away past the rev limiter

    @property
    def speed_kmh(self) -> float:
        return abs(self.speed_ms) * 3.6

    @property
    def fuel_pct(self) -> float:
        return self.fuel_l / FUEL_TANK_L * 100.0

    def step(self, dt: float, act: Actuators, driver: DriverInputs) -> None:
        fueled = act.fuel_enabled and self.fuel_l > 0.0
        # Drive-by-wire: the engine follows the ECM's throttle command, not the pedal.
        throttle = min(max(act.throttle, 0.0), 100.0) / 100.0 if fueled else 0.0
        gear = act.drive_gear

        self._step_engine(dt, fueled, throttle, gear, act.torque_limit)
        drive_n = self._drive_force(throttle, gear, act.shifting) if fueled else 0.0

        resist_n = p.MAX_BRAKE_FORCE_N * min(max(driver.brake, 0.0), 100.0) / 100.0
        resist_n += p.ROLLING_RESISTANCE_N
        if act.park:
            resist_n += p.PARK_HOLD_FORCE_N
        self.speed_ms = p.integrate_speed(self.speed_ms, drive_n, resist_n, dt)
        self.odometer_km += abs(self.speed_ms) * dt / 1000.0

        self._step_thermal(dt, coupled=gear is not None)
        self._step_fuel(dt, throttle)

    def _step_engine(
        self, dt: float, fueled: bool, throttle: float, gear: int | None, torque_limit: float
    ) -> None:
        if not fueled:
            self.engine_rpm = p.first_order(self.engine_rpm, 0.0, 0.5, dt)
            self.engine_torque_nm = 0.0
            self.engine_load = 0.0
            self.engine_running = False
            return

        if gear is None:
            target = p.IDLE_RPM + throttle * (p.FREE_REV_MAX_RPM - p.IDLE_RPM)
        else:
            stall = p.IDLE_RPM + throttle * (p.STALL_RPM - p.IDLE_RPM)
            target = max(p.wheel_to_engine_rpm(self.speed_ms, gear), stall)
        target = OVERSPEED_RPM if self.overspeed else min(target, p.REV_LIMIT_RPM)
        self.engine_rpm = p.first_order(self.engine_rpm, target, 0.25, dt)

        available = p.max_engine_torque(self.engine_rpm) * torque_limit
        produced = throttle * available
        if self.engine_rpm >= p.REV_LIMIT_RPM - 1.0:
            produced = 0.0  # rev limiter cuts fuel
        self.engine_torque_nm = produced - p.engine_friction_torque(self.engine_rpm)
        self.engine_load = produced / available if available > 0 else 0.0
        self.engine_running = self.engine_rpm > 400.0

    def _drive_force(self, throttle: float, gear: int | None, shifting: bool) -> float:
        if gear is None or not self.engine_running:
            return 0.0

        wheel_rpm_at_engine = p.wheel_to_engine_rpm(self.speed_ms, gear)
        stall = p.IDLE_RPM + throttle * (p.STALL_RPM - p.IDLE_RPM)
        if wheel_rpm_at_engine < stall:
            # Converter slipping: passes positive torque plus idle creep, never engine braking.
            creep = p.CREEP_TORQUE_NM * max(0.0, 1.0 - wheel_rpm_at_engine / p.IDLE_RPM)
            torque = max(self.engine_torque_nm, 0.0) + creep
        else:
            torque = self.engine_torque_nm

        if shifting:
            torque *= p.SHIFT_TORQUE_FACTOR
        return p.wheel_force(torque, gear)

    def _step_thermal(self, dt: float, coupled: bool) -> None:
        if self.engine_running:
            # Thermostat holds coolant near 88 C; sustained load pushes it higher.
            # A failed cooling system lets it climb far past the overheat point.
            extra = 45.0 if self.cooling_failure else 0.0
            self.coolant_c = p.first_order(
                self.coolant_c, 88.0 + 14.0 * self.engine_load + extra, 25.0, dt
            )
            self.oil_c = p.first_order(
                self.oil_c, 90.0 + 25.0 * self.engine_load + extra / 2, 40.0, dt
            )
        else:
            self.coolant_c = p.first_order(self.coolant_c, p.AMBIENT_C, 180.0, dt)
            self.oil_c = p.first_order(self.oil_c, p.AMBIENT_C, 240.0, dt)

        if self.engine_running and coupled:
            # Without the oil cooler the fluid heats quickly toward a much higher level.
            extra, tau = (80.0, 20.0) if self.trans_cooling_failure else (0.0, 40.0)
            self.trans_c = p.first_order(
                self.trans_c, 65.0 + 30.0 * self.engine_load + extra, tau, dt
            )
        else:
            self.trans_c = p.first_order(self.trans_c, p.AMBIENT_C, 240.0, dt)

    def _step_fuel(self, dt: float, throttle: float) -> None:
        self.fuel_l = max(0.0, self.fuel_l - self.fuel_leak_lps * dt)
        if not self.engine_running:
            return
        litres_per_s = 0.00025 + 0.011 * throttle * self.engine_rpm / p.REV_LIMIT_RPM
        self.fuel_l = max(0.0, self.fuel_l - litres_per_s * FUEL_CONSUMPTION_SCALE * dt)
