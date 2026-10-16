"""Integration tests against a real Linux SocketCAN interface.

They run only where the interface exists (create it with scripts/setup_vcan.sh;
CI does this in its socketcan job) and are skipped everywhere else. Set
CAN_TEST_CHANNEL to use an interface other than vcan0. Nothing else may be
sending on that interface while they run.
"""

import os
import time
from collections import Counter

import pytest

from app.can import bus as bus_module
from app.can.bus import BusFactory, CanBackend
from app.can.decoder import CanCodec
from app.config import CanMode
from app.simulation.simulator import TICK_S, Simulator

CHANNEL = os.environ.get("CAN_TEST_CHANNEL", "vcan0")
_unavailable = bus_module._probe_socketcan(CHANNEL)

if _unavailable and os.environ.get("CAN_TEST_REQUIRED"):
    # CI's socketcan job sets this: a missing interface must fail, not skip.
    raise RuntimeError(f"CAN_TEST_REQUIRED is set but SocketCAN is unavailable: {_unavailable}")

pytestmark = pytest.mark.skipif(
    _unavailable is not None, reason=f"SocketCAN not available: {_unavailable}"
)


@pytest.fixture
def factory() -> BusFactory:
    return BusFactory(CanMode.SOCKETCAN, CHANNEL)


def test_auto_mode_picks_socketcan() -> None:
    assert BusFactory(CanMode.AUTO, CHANNEL).backend is CanBackend.SOCKETCAN


def test_frames_travel_over_the_kernel_bus(factory: BusFactory, codec: CanCodec) -> None:
    sender, receiver = factory.open(), factory.open()
    try:
        frame = codec.encode(
            "BODY_STATUS",
            {
                "FuelLevel": 50,
                "Headlights": "LOW",
                "TurnIndicator": "OFF",
                "BrakeLights": 0,
                "DoorFrontLeftOpen": 0,
                "DoorFrontRightOpen": 0,
                "DoorRearLeftOpen": 0,
                "DoorRearRightOpen": 0,
                "SeatbeltFastened": 1,
            },
            counter=3,
        )
        sender.send(frame)

        received = receiver.recv(timeout=1.0)

        assert received is not None
        decoded = codec.decode(received)
        assert decoded.ok, decoded.error_detail
        assert decoded.name == "BODY_STATUS"
        assert decoded.signals["Headlights"] == "LOW"
    finally:
        sender.shutdown()
        receiver.shutdown()


def test_full_network_runs_on_socketcan(factory: BusFactory, codec: CanCodec) -> None:
    sniffer = factory.open()
    try:
        with Simulator(factory, codec, seed=1) as sim:
            sim.driver.ignition = True
            # Paced in real time like the backend, so the kernel delivers
            # frames between ticks the way it does in production.
            start = time.perf_counter()
            for tick in range(1, round(2.0 / TICK_S) + 1):
                sim.step()
                time.sleep(max(0.0, start + tick * TICK_S - time.perf_counter()))

            seen: Counter[str] = Counter()
            while (frame := sniffer.recv(timeout=0.1)) is not None:
                decoded = codec.decode(frame)
                assert decoded.ok, decoded.error_detail
                seen[decoded.name] += 1

            assert sim.dashboard.view()["engine_state"] == "IDLE"
            assert all(sim.dashboard.view()["sources_online"].values())
    finally:
        sniffer.shutdown()

    # Every ECU's messages crossed the kernel bus at roughly their DBC rates.
    assert seen["VEHICLE_STATUS"] >= 30  # 50 ms cycle over 2 s
    assert seen["ENGINE_STATUS"] >= 15
    assert {"ENGINE_TEMPERATURE", "BODY_STATUS", "DASHBOARD_STATUS"} <= seen.keys()
