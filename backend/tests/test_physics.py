import pytest

from app.simulation import physics as p
from app.simulation.sensors import Sensor
from app.simulation.vehicle import Actuators, DriverInputs, VehicleModel


def test_torque_curve_interpolates_between_points() -> None:
    assert p.max_engine_torque(4000) == 250
    assert p.max_engine_torque(3000) == pytest.approx(230)
    assert p.max_engine_torque(9000) == p.TORQUE_CURVE[-1][1]


def test_speed_to_engine_rpm_through_gearing() -> None:
    # 100 km/h in 6th: 27.78 m/s / 0.31 m * 0.65 * 3.7 -> ~2058 rpm
    assert p.kmh_to_engine_rpm(100, 6) == pytest.approx(2058, rel=0.01)
    assert p.kmh_to_engine_rpm(100, 1) > p.kmh_to_engine_rpm(100, 2)


def test_brakes_hold_a_stationary_car_against_drive_force() -> None:
    assert p.integrate_speed(0.0, drive_n=500, resist_n=2000, dt=0.01) == 0.0


def test_friction_stops_the_car_without_reversing_it() -> None:
    assert p.integrate_speed(0.05, drive_n=0, resist_n=10_000, dt=0.01) == 0.0
    assert p.integrate_speed(-0.05, drive_n=0, resist_n=10_000, dt=0.01) == 0.0


def test_drag_slows_a_coasting_car() -> None:
    speed = 30.0
    for _ in range(100):
        speed = p.integrate_speed(speed, 0.0, p.ROLLING_RESISTANCE_N, 0.01)
    assert 28.0 < speed < 30.0


def test_first_order_lag_reaches_63_percent_after_one_time_constant() -> None:
    value = 0.0
    for _ in range(100):
        value = p.first_order(value, 100.0, tau_s=1.0, dt=0.01)
    assert value == pytest.approx(63.2, abs=0.1)


def run_plant(plant: VehicleModel, act: Actuators, driver: DriverInputs, seconds: float) -> None:
    for _ in range(round(seconds / 0.01)):
        plant.step(0.01, act, driver)


def test_engine_does_not_run_without_fuel_command() -> None:
    plant = VehicleModel()

    run_plant(plant, Actuators(fuel_enabled=False, throttle=100), DriverInputs(), 2.0)

    assert plant.engine_rpm == 0.0
    assert not plant.engine_running


def test_park_holds_the_car_at_full_throttle() -> None:
    plant = VehicleModel()

    run_plant(plant, Actuators(fuel_enabled=True, park=True, throttle=100), DriverInputs(), 3.0)

    assert plant.speed_ms == 0.0
    assert plant.engine_rpm > 5000  # free-revving


def test_throttle_accelerates_and_brake_stops_without_reversing() -> None:
    plant = VehicleModel()
    act = Actuators(fuel_enabled=True, drive_gear=1, park=False, throttle=50)

    run_plant(plant, act, DriverInputs(), 3.0)
    moving = plant.speed_kmh
    act.throttle = 0
    run_plant(plant, act, DriverInputs(brake=100), 5.0)

    assert moving > 15
    assert plant.speed_ms == 0.0


def test_reverse_gear_moves_backwards() -> None:
    plant = VehicleModel()

    run_plant(
        plant,
        Actuators(fuel_enabled=True, drive_gear=-1, park=False, throttle=20),
        DriverInputs(),
        2.0,
    )

    assert plant.speed_ms < 0
    assert plant.speed_kmh > 0


def test_temperatures_rise_under_load_and_fall_when_load_drops() -> None:
    plant = VehicleModel(coolant_c=88.0, oil_c=90.0)
    act = Actuators(fuel_enabled=True, drive_gear=3, park=False, throttle=100)

    run_plant(plant, act, DriverInputs(), 30.0)
    hot = plant.coolant_c, plant.oil_c
    act.throttle = 0
    run_plant(plant, act, DriverInputs(), 30.0)

    assert hot[0] > 95 and hot[1] > 100
    assert plant.coolant_c < hot[0] and plant.oil_c < hot[1]


def test_fuel_is_consumed_only_while_running() -> None:
    plant = VehicleModel()
    start = plant.fuel_l

    run_plant(plant, Actuators(fuel_enabled=False), DriverInputs(), 5.0)
    assert plant.fuel_l == start
    run_plant(plant, Actuators(fuel_enabled=True, throttle=50), DriverInputs(), 5.0)
    assert plant.fuel_l < start


def test_engine_stops_when_tank_runs_dry() -> None:
    plant = VehicleModel(fuel_l=0.0)

    run_plant(plant, Actuators(fuel_enabled=True), DriverInputs(), 2.0)

    assert not plant.engine_running


def test_pulse_sensor_reads_exact_zero_when_stationary() -> None:
    sensor = Sensor(lambda: 0.0, noise_std=1.0, minimum=0.0, zero_below=0.05)
    moving = Sensor(lambda: 50.0, noise_std=1.0, minimum=0.0, zero_below=0.05)

    assert {sensor.read() for _ in range(50)} == {0.0}
    assert len({moving.read() for _ in range(50)}) > 1
