"""Run the ECU network in real time with a scripted drive and print live values.

Run from the repository root:
    python scripts/start_simulation.py           # full ~60 s drive
    python scripts/start_simulation.py --fast    # same drive, no real-time waiting
    python scripts/start_simulation.py --demo    # Demo Mode sequence (with faults)

Values printed come from a passive CAN sniffer decoding the bus traffic, the
same way the dashboard will see them, not from the simulation internals.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.can.bus import BusFactory  # noqa: E402
from app.can.dbc_loader import load_database  # noqa: E402
from app.can.decoder import CanCodec  # noqa: E402
from app.config import settings  # noqa: E402
from app.simulation.demo import DemoDirector  # noqa: E402
from app.simulation.simulator import TICK_S, Simulator  # noqa: E402
from app.simulation.vehicle import DriverInputs, Headlights, Selector  # noqa: E402

# (duration s, label, driver changes)
DRIVE: list[tuple[float, str, dict]] = [
    (2, "ignition on", {"ignition": True}),
    (1, "brake + D", {"brake": 50, "gear_selector": Selector.D, "headlights": Headlights.LOW}),
    (3, "idle creep", {"brake": 0}),
    (15, "accelerate 60%", {"throttle": 60}),
    (10, "cruise 20%", {"throttle": 20}),
    (5, "coast", {"throttle": 0}),
    (6, "brake 60%", {"brake": 60}),
    (10, "full throttle", {"brake": 0, "throttle": 100}),
    (6, "hard stop", {"throttle": 0, "brake": 100}),
    (2, "park", {"gear_selector": Selector.P}),
    (2, "ignition off", {"ignition": False, "brake": 0, "headlights": Headlights.OFF}),
]

HEADER = (
    f"{'time':>5}  {'phase':<15} {'engine':<12} {'sel':>3} {'gear':>4} "
    f"{'km/h':>6} {'rpm':>5} {'load':>4} {'cool':>4} {'oil':>4} {'trans':>5} {'fuel':>5}"
)


def apply(driver: DriverInputs, changes: dict) -> None:
    for key, value in changes.items():
        setattr(driver, key, value)


def drive_ticks(sim: Simulator) -> Iterator[str]:
    """The fixed drive: yields the phase label once per tick."""
    for duration, label, changes in DRIVE:
        apply(sim.driver, changes)
        for _ in range(round(duration / TICK_S)):
            yield label


def demo_ticks(sim: Simulator) -> Iterator[str]:
    """The Demo Mode director, announcing each step as it starts."""
    director = DemoDirector(sim)
    shown = -1
    while director.active:
        if director.index != shown:
            shown = director.index
            step = director.steps[shown]
            print(f"\n==> {shown + 1}/{len(director.steps)} {step.title}: {step.caption}")
        yield director.steps[shown].title
        director.step()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fast", action="store_true", help="do not wait for wall-clock time")
    parser.add_argument("--demo", action="store_true", help="run the Demo Mode sequence")
    args = parser.parse_args()
    # Captions contain "→"; don't crash on consoles or pipes that can't show it.
    sys.stdout.reconfigure(errors="replace")  # type: ignore[union-attr]

    codec = CanCodec(load_database())
    factory = BusFactory(settings.can_mode, settings.can_channel)
    print(f"CAN backend: {factory.backend}\n")
    sniffer = factory.open()
    latest: dict[str, dict] = {}
    counts: Counter[str] = Counter()

    with Simulator(factory, codec) as sim:
        print(HEADER)
        deadline = time.perf_counter()
        ticks = demo_ticks(sim) if args.demo else drive_ticks(sim)
        for tick, label in enumerate(ticks):
            sim.step()
            while (frame := sniffer.recv(timeout=0)) is not None:
                decoded = codec.decode(frame)
                counts[decoded.name or f"0x{decoded.arbitration_id:03X}"] += 1
                if decoded.ok:
                    latest[decoded.name] = decoded.signals
            if tick % 50 == 49 and len(latest) >= 4:
                print_row(sim.time, label, latest)
            if not args.fast:
                deadline += TICK_S
                time.sleep(max(0.0, deadline - time.perf_counter()))
        elapsed = sim.time
    sniffer.shutdown()

    print(f"\nCAN traffic over {elapsed:.0f} s of simulated time:")
    for name, n in sorted(counts.items()):
        print(f"  {name:<20} {n:6d} frames  {n / elapsed:5.1f} /s")


def print_row(t: float, label: str, latest: dict[str, dict]) -> None:
    eng = latest.get("ENGINE_STATUS", {})
    temp = latest.get("ENGINE_TEMPERATURE", {})
    veh = latest.get("VEHICLE_STATUS", {})
    tr = latest.get("TRANSMISSION_STATUS", {})
    body = latest.get("BODY_STATUS", {})
    print(
        f"{t:5.1f}  {label[:15]:<15} {eng.get('EngineState', '-'):<12} "
        f"{tr.get('GearSelector', '-'):>3} {tr.get('CurrentGear', 0) or '-':>4} "
        f"{veh.get('VehicleSpeed', 0):6.1f} {eng.get('EngineRPM', 0):5.0f} "
        f"{eng.get('EngineLoad', 0):4.0f} {temp.get('CoolantTemp', 0):4.0f} "
        f"{temp.get('OilTemp', 0):4.0f} {tr.get('TransTemp', 0):5.0f} "
        f"{body.get('FuelLevel', 0):5.1f}"
    )


if __name__ == "__main__":
    main()
