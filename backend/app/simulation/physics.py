"""Simplified longitudinal vehicle physics.

This is a believable teaching model, not a validated vehicle model: a
point-mass car with an engine torque curve, a torque converter reduced to
"slipping below stall speed, locked above it", aerodynamic drag, rolling
resistance and a linear brake. Every function here is pure so it can be
tested in isolation.
"""

from __future__ import annotations

import math

# Vehicle
MASS_KG = 1500.0
WHEEL_RADIUS_M = 0.31
DRAG_COEFF = 0.4  # 0.5 * air density * Cd * frontal area, N/(m/s)^2
ROLLING_RESISTANCE_N = 0.012 * MASS_KG * 9.81
MAX_BRAKE_FORCE_N = 11_000.0  # ~0.75 g at full pedal
PARK_HOLD_FORCE_N = 20_000.0

# Engine
IDLE_RPM = 800.0
STALL_RPM = 2800.0  # converter stall speed at full throttle
REV_LIMIT_RPM = 6800.0
FREE_REV_MAX_RPM = 6000.0  # full throttle with no gear engaged
CREEP_TORQUE_NM = 20.0
TORQUE_CURVE = [  # (rpm, full-load torque Nm)
    (0.0, 0.0),
    (800.0, 140.0),
    (2000.0, 210.0),
    (4000.0, 250.0),
    (5500.0, 235.0),
    (6500.0, 190.0),
    (REV_LIMIT_RPM, 170.0),
]

# Driveline
GEAR_RATIOS = (3.5, 2.1, 1.4, 1.0, 0.8, 0.65)
REVERSE_RATIO = 3.2
FINAL_DRIVE = 3.7
DRIVELINE_EFFICIENCY = 0.85
SHIFT_TORQUE_FACTOR = 0.3  # torque passed through while a shift is in progress

AMBIENT_C = 20.0


def interpolate(points: list[tuple[float, float]], x: float) -> float:
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]


def max_engine_torque(rpm: float) -> float:
    return interpolate(TORQUE_CURVE, rpm)


def engine_friction_torque(rpm: float) -> float:
    """Pumping and friction losses; this is what gives engine braking."""
    return 10.0 + 0.004 * rpm


def overall_ratio(gear: int) -> float:
    """Engine-to-wheel ratio; gear 1-6 forward, -1 reverse."""
    if gear == -1:
        return REVERSE_RATIO * FINAL_DRIVE
    return GEAR_RATIOS[gear - 1] * FINAL_DRIVE


def wheel_to_engine_rpm(speed_ms: float, gear: int) -> float:
    wheel_rad_s = abs(speed_ms) / WHEEL_RADIUS_M
    return wheel_rad_s * overall_ratio(gear) * 60.0 / (2.0 * math.pi)


def kmh_to_engine_rpm(speed_kmh: float, gear: int) -> float:
    return wheel_to_engine_rpm(speed_kmh / 3.6, gear)


def wheel_force(engine_torque_nm: float, gear: int) -> float:
    """Tractive force at the wheels, signed: positive pushes forward."""
    force = engine_torque_nm * overall_ratio(gear) * DRIVELINE_EFFICIENCY / WHEEL_RADIUS_M
    return -force if gear == -1 else force


def drag_force(speed_ms: float) -> float:
    return DRAG_COEFF * speed_ms * abs(speed_ms)


def first_order(current: float, target: float, tau_s: float, dt: float) -> float:
    """Move ``current`` toward ``target`` like a first-order lag (RC filter)."""
    return current + (target - current) * (1.0 - math.exp(-dt / tau_s))


def integrate_speed(
    speed_ms: float, drive_n: float, resist_n: float, dt: float, mass_kg: float = MASS_KG
) -> float:
    """Advance signed speed by one step.

    ``resist_n`` (brakes, rolling resistance) always opposes motion and, like
    real friction, can stop the car but never push it backwards.
    """
    if abs(speed_ms) < 1e-3:
        if abs(drive_n) <= resist_n:
            return 0.0
        net = drive_n - math.copysign(resist_n, drive_n)
        return net / mass_kg * dt

    net = drive_n - drag_force(speed_ms) - math.copysign(resist_n, speed_ms)
    new_speed = speed_ms + net / mass_kg * dt
    if new_speed * speed_ms < 0 and abs(drive_n) <= resist_n:
        return 0.0  # friction brought us to a stop this step
    return new_speed
