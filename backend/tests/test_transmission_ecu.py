from app.ecus.transmission import gear_for_speed
from app.simulation.simulator import Simulator
from app.simulation.vehicle import Selector

from .helpers import start_and_select_drive


def gears_over(sim: Simulator, seconds: float) -> list[int]:
    gears = []
    for _ in range(round(seconds / 0.01)):
        sim.step()
        gears.append(sim.transmission.gear)
    return gears


def test_gear_for_speed_picks_low_gear_when_slow_and_high_when_fast() -> None:
    assert gear_for_speed(0, throttle=0) == 1
    assert gear_for_speed(100, throttle=0) >= 5
    assert gear_for_speed(100, throttle=100) < gear_for_speed(100, throttle=0)


def test_leaving_park_requires_the_brake(sim: Simulator) -> None:
    sim.driver.ignition = True
    sim.run_for(1.5)

    sim.driver.gear_selector = Selector.D
    sim.run_for(0.2)
    assert sim.transmission.selector is Selector.P

    sim.driver.brake = 50
    sim.run_for(0.2)
    assert sim.transmission.selector is Selector.D
    assert sim.transmission.gear == 1


def test_park_and_reverse_refused_while_moving(sim: Simulator) -> None:
    start_and_select_drive(sim)
    sim.driver.throttle = 50
    sim.run_for(4.0)

    for refused in (Selector.R, Selector.P):
        sim.driver.gear_selector = refused
        sim.run_for(0.2)
        assert sim.transmission.selector is Selector.D


def test_upshifts_progressively_under_steady_throttle(sim: Simulator) -> None:
    start_and_select_drive(sim)
    sim.driver.throttle = 60

    gears = gears_over(sim, 20.0)

    assert gears == sorted(gears), "no downshift while accelerating"
    assert gears[-1] >= 3


def test_braking_downshifts_back_to_first(sim: Simulator) -> None:
    start_and_select_drive(sim)
    sim.driver.throttle = 70
    sim.run_for(15.0)
    assert sim.transmission.gear >= 3

    sim.driver.throttle = 0
    sim.driver.brake = 60
    sim.run_for(8.0)

    assert sim.vehicle.speed_kmh == 0
    assert sim.transmission.gear == 1


def test_kickdown_on_full_throttle(sim: Simulator) -> None:
    start_and_select_drive(sim)
    sim.driver.throttle = 60
    sim.run_for(15.0)
    sim.driver.throttle = 20
    sim.run_for(5.0)
    cruising_gear = sim.transmission.gear

    sim.driver.throttle = 100
    sim.run_for(1.0)

    assert sim.transmission.gear < cruising_gear


def test_no_gear_hunting_while_cruising(sim: Simulator) -> None:
    start_and_select_drive(sim)
    sim.driver.throttle = 60
    sim.run_for(15.0)
    sim.driver.throttle = 25
    sim.run_for(5.0)

    gears = gears_over(sim, 10.0)

    assert len(set(gears)) == 1


def test_shift_in_progress_flag_is_brief(sim: Simulator) -> None:
    start_and_select_drive(sim)
    sim.driver.throttle = 60

    flags = []
    for _ in range(1500):
        sim.step()
        flags.append(sim.transmission.shifting)

    assert any(flags)
    assert sum(flags) < 0.2 * len(flags)


def test_no_upshift_while_braking(sim: Simulator) -> None:
    start_and_select_drive(sim)
    sim.driver.throttle = 100
    sim.run_for(9.0)

    sim.driver.throttle = 0
    sim.driver.brake = 100
    gears = gears_over(sim, 6.0)

    assert gears == sorted(gears, reverse=True)
    assert gears[-1] == 1


def test_stationary_vehicle_reports_exactly_zero_speed(sim: Simulator) -> None:
    start_and_select_drive(sim)
    sim.driver.brake = 60
    sim.run_for(1.0)

    assert sim.transmission.signals_for("VEHICLE_STATUS")["VehicleSpeed"] == 0.0
