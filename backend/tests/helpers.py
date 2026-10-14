from app.simulation.simulator import Simulator
from app.simulation.vehicle import Selector


def start_and_select_drive(sim: Simulator) -> None:
    """Ignition on, wait for idle, then brake + D (the shift lock needs the brake)."""
    sim.driver.ignition = True
    sim.run_for(1.5)
    sim.driver.brake = 50
    sim.driver.gear_selector = Selector.D
    sim.run_for(0.2)
    sim.driver.brake = 0
