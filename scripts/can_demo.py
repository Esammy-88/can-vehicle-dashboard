"""Phase 2 demo: watch DBC-encoded frames travel between simulated ECU nodes.

Run from the repository root:
    python scripts/can_demo.py

Three nodes (ECM, TCM, BCM) share one bus with a listening instrument cluster
(IPC). The ECM ramps RPM up, then a corrupted frame and an unknown ID are
injected to show how the decoder flags bad traffic instead of crashing.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import can  # noqa: E402

from app.can.bus import BusFactory  # noqa: E402
from app.can.dbc_loader import load_database  # noqa: E402
from app.can.decoder import CanCodec  # noqa: E402
from app.config import settings  # noqa: E402


def show(codec: CanCodec, frame: can.Message) -> None:
    d = codec.decode(frame)
    data = " ".join(f"{b:02X}" for b in d.data)
    name = d.name or "?"
    status = "OK " if d.ok else f"ERR {d.error}"
    signals = ", ".join(
        f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}"
        for k, v in d.signals.items()
        if k not in ("AliveCounter", "Checksum")
    )
    print(f"0x{d.arbitration_id:03X}  {name:<20} {data:<23}  {status:<16} {signals}")


def main() -> None:
    codec = CanCodec(load_database())
    factory = BusFactory(settings.can_mode, settings.can_channel)
    print(f"CAN backend: {factory.backend} (CAN_MODE={settings.can_mode})\n")

    ecm, tcm, bcm, ipc = (factory.open() for _ in range(4))
    try:
        print("ID     MESSAGE              DATA                     STATUS           SIGNALS")
        for counter, rpm in enumerate((800, 1500, 2450, 3200)):
            ecm.send(
                codec.encode(
                    "ENGINE_STATUS",
                    {
                        "EngineRPM": rpm,
                        "EngineLoad": rpm / 50,
                        "ThrottlePosition": rpm / 60,
                        "EngineRunning": 1,
                        "EngineState": "IDLE" if rpm < 1000 else "ACCELERATING",
                    },
                    counter=counter,
                )
            )
            tcm.send(
                codec.encode(
                    "VEHICLE_STATUS",
                    {"VehicleSpeed": rpm / 40, "BrakeSwitch": 0},
                    counter=counter,
                )
            )
            time.sleep(0.1)

        bcm.send(
            codec.encode(
                "BODY_STATUS",
                {
                    "FuelLevel": 67.5,
                    "Headlights": "LOW",
                    "TurnIndicator": "LEFT",
                    "DoorFrontLeftOpen": 1,
                    "DoorFrontRightOpen": 0,
                    "DoorRearLeftOpen": 0,
                    "DoorRearRightOpen": 0,
                    "SeatbeltFastened": 0,
                    "BrakeLights": 0,
                },
            )
        )

        corrupted = codec.encode(
            "ENGINE_TEMPERATURE",
            {"CoolantTemp": 91, "OilTemp": 104, "EngineDtc": 0, "EngineDtcCount": 0},
        )
        corrupted.data[0] ^= 0xFF  # simulate a bit-flipped payload
        ecm.send(corrupted)
        ecm.send(can.Message(arbitration_id=0x6AB, data=bytes(8), is_extended_id=False))

        while (frame := ipc.recv(timeout=0.2)) is not None:
            show(codec, frame)
    finally:
        for bus in (ecm, tcm, bcm, ipc):
            bus.shutdown()


if __name__ == "__main__":
    main()
