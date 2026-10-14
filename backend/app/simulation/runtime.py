"""Runs the Simulator in real time inside the backend's asyncio event loop.

The loop wakes roughly every tick and runs however many 10 ms simulation
steps the elapsed wall time (x speed factor) calls for. Catching up this way
keeps simulated time accurate even when the OS timer is coarse (Windows often
sleeps ~15 ms when asked for 10). Everything runs on the event loop thread,
so REST handlers can change driver inputs without locks.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import asdict
from typing import Any

from app.can.bus import BusFactory
from app.can.decoder import CanCodec
from app.simulation.simulator import TICK_S, Simulator

log = logging.getLogger(__name__)

SPEED_FACTORS = (0.5, 1.0, 2.0, 5.0)
MAX_TICKS_PER_WAKE = 50  # after a long stall, skip ahead rather than spin to catch up


class SimulationRuntime:
    def __init__(self, factory: BusFactory, codec: CanCodec, seed: int = 0) -> None:
        self.factory = factory
        self._codec = codec
        self._seed = seed
        self.sim = Simulator(factory, codec, seed)
        self.running = True
        self.speed = 1.0
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="simulation")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self.sim.close()

    def resume(self) -> None:
        self.running = True

    def pause(self) -> None:
        self.running = False

    def reset(self) -> None:
        self.sim.close()
        self.sim = Simulator(self.factory, self._codec, self._seed)

    def set_speed(self, factor: float) -> None:
        if factor not in SPEED_FACTORS:
            raise ValueError(f"speed must be one of {SPEED_FACTORS}")
        self.speed = factor

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "speed": self.speed,
            "time_s": round(self.sim.time, 2),
            "crashed_ecus": sorted(self.sim.crashed),
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "simulation": self.status(),
            "can_backend": self.factory.backend.value,
            "can_mode": self.factory.mode.value,
            "cluster": self.sim.dashboard.view(),
            "controls": asdict(self.sim.driver),
        }

    async def _loop(self) -> None:
        loop = asyncio.get_running_loop()
        last = loop.time()
        owed = 0.0  # simulated seconds we still owe the wall clock
        while True:
            await asyncio.sleep(TICK_S)
            now = loop.time()
            elapsed, last = now - last, now
            if not self.running:
                continue
            owed += elapsed * self.speed
            ticks = int(owed / TICK_S)
            if ticks > MAX_TICKS_PER_WAKE:
                ticks, owed = MAX_TICKS_PER_WAKE, MAX_TICKS_PER_WAKE * TICK_S
            owed -= ticks * TICK_S
            try:
                for _ in range(ticks):
                    self.sim.step()
            except Exception:
                log.exception("Simulation step failed; pausing")
                self.running = False
