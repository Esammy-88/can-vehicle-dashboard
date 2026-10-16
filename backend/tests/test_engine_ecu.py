from app.ecus.engine import LIMP_TORQUE_LIMIT, EngineState
from app.simulation.simulator import Simulator
from app.simulation.vehicle import Selector

from .helpers import start_and_select_drive


def test_ignition_starts_engine_to_idle(sim: Simulator) -> None:
    sim.driver.ignition = True
    sim.step()
    assert sim.engine.state is EngineState.STARTING

    sim.run_for(1.0)

    assert sim.engine.state is EngineState.IDLE
    assert 700 < sim.vehicle.engine_rpm < 900


def test_ignition_off_stops_engine(sim: Simulator) -> None:
    sim.driver.ignition = True
    sim.run_for(1.5)
    sim.driver.ignition = False
    sim.run_for(3.0)

    assert sim.engine.state is EngineState.OFF
    assert sim.vehicle.engine_rpm < 50


def test_revving_in_neutral_is_accelerating(sim: Simulator) -> None:
    sim.driver.ignition = True
    sim.run_for(1.5)
    sim.driver.brake = 50
    sim.driver.gear_selector = Selector.N
    sim.run_for(0.2)
    sim.driver.brake = 0  # brake + throttle together would trigger the brake override
    sim.driver.throttle = 60
    sim.run_for(0.3)

    assert sim.engine.state is EngineState.ACCELERATING


def test_driving_states_follow_throttle(sim: Simulator) -> None:
    start_and_select_drive(sim)

    sim.driver.throttle = 60
    sim.run_for(5.0)
    assert sim.engine.state is EngineState.ACCELERATING

    sim.driver.throttle = 0
    sim.run_for(2.0)
    assert sim.engine.state is EngineState.DECELERATING

    sim.driver.throttle = 20
    sim.run_for(5.0)
    assert sim.engine.state is EngineState.CRUISING


def test_overheat_enters_limp_mode_and_recovers(sim: Simulator) -> None:
    sim.driver.ignition = True
    sim.run_for(1.5)

    sim.vehicle.coolant_c = 120.0
    sim.run_for(0.1)
    assert sim.engine.state is EngineState.OVERHEAT
    assert sim.engine.torque_limit == LIMP_TORQUE_LIMIT

    sim.vehicle.coolant_c = 108.0  # still above the exit threshold (hysteresis)
    sim.run_for(0.1)
    assert sim.engine.state is EngineState.OVERHEAT

    sim.vehicle.coolant_c = 95.0
    sim.run_for(0.1)
    assert sim.engine.state is EngineState.IDLE
    assert sim.engine.torque_limit == 1.0


def test_running_out_of_fuel_latches_fault_until_ignition_cycle(sim: Simulator) -> None:
    sim.driver.ignition = True
    sim.run_for(1.5)

    sim.vehicle.fuel_l = 0.0
    sim.run_for(3.0)
    assert sim.engine.state is EngineState.FAULT
    assert not sim.engine.fuel_enabled

    sim.vehicle.fuel_l = 20.0
    sim.run_for(1.0)
    assert sim.engine.state is EngineState.FAULT

    sim.driver.ignition = False
    sim.run_for(0.1)
    sim.driver.ignition = True
    sim.run_for(1.5)
    assert sim.engine.state is EngineState.IDLE


def test_engine_learns_vehicle_speed_over_can(sim: Simulator) -> None:
    start_and_select_drive(sim)
    sim.driver.throttle = 50
    sim.run_for(5.0)

    assert abs(sim.engine.vehicle_speed_kmh - sim.vehicle.speed_kmh) < 2.0


def test_stopped_engine_reports_zero_load(sim: Simulator) -> None:
    sim.run_for(1.0)

    assert sim.engine.signals_for("ENGINE_STATUS")["EngineLoad"] == 0.0
