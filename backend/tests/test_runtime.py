import asyncio
import json
from collections.abc import AsyncIterator

import pytest

from app.can.bus import BusFactory
from app.can.decoder import CanCodec
from app.simulation.runtime import SimulationRuntime


@pytest.fixture
async def runtime(factory: BusFactory, codec: CanCodec) -> AsyncIterator[SimulationRuntime]:
    rt = SimulationRuntime(factory, codec)
    rt.start()
    yield rt
    await rt.stop()


async def test_simulated_time_tracks_wall_clock(runtime: SimulationRuntime) -> None:
    await asyncio.sleep(1.0)

    assert 0.8 <= runtime.sim.time <= 1.2


async def test_speed_factor_runs_faster(runtime: SimulationRuntime) -> None:
    runtime.set_speed(5.0)
    await asyncio.sleep(0.6)

    assert runtime.sim.time > 2.0


async def test_pause_and_resume(runtime: SimulationRuntime) -> None:
    await asyncio.sleep(0.2)
    runtime.pause()
    paused_at = runtime.sim.time
    await asyncio.sleep(0.3)
    assert runtime.sim.time == paused_at

    runtime.resume()
    await asyncio.sleep(0.3)
    assert runtime.sim.time > paused_at


async def test_reset_gives_fresh_simulation(runtime: SimulationRuntime) -> None:
    runtime.sim.driver.ignition = True
    await asyncio.sleep(0.3)

    runtime.reset()

    assert runtime.sim.time == 0.0
    assert runtime.sim.driver.ignition is False


async def test_invalid_speed_rejected(runtime: SimulationRuntime) -> None:
    with pytest.raises(ValueError):
        runtime.set_speed(3.0)


async def test_snapshot_is_json_serialisable(runtime: SimulationRuntime) -> None:
    await asyncio.sleep(0.3)

    json.dumps(runtime.snapshot())
