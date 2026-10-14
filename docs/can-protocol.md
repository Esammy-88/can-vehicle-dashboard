# CAN Protocol

The network is described in [`dbc/vehicle.dbc`](../dbc/vehicle.dbc), which is
the single source of truth for IDs, signal layout, scaling and cycle times.
All frames are classic CAN 2.0A: standard 11-bit identifiers, 8-byte payload,
little-endian (Intel) signals.

## Nodes

| Node | ECU |
|---|---|
| ECM | Engine Control Module |
| TCM | Transmission Control Module |
| BCM | Body Control Module |
| IPC | Instrument Panel Cluster (dashboard ECU) |
| DIAG | Diagnostic monitor |

## Messages

Lower IDs win arbitration, so the safety-relevant powertrain data (0x1xx,
0x2xx) has priority over body, cluster and diagnostic traffic.

| ID | Message | Sender | Cycle | Signals |
|---|---|---|---|---|
| 0x100 | ENGINE_STATUS | ECM | 100 ms | EngineRPM, EngineLoad, ThrottlePosition, EngineRunning, EngineState |
| 0x101 | ENGINE_TEMPERATURE | ECM | 500 ms | CoolantTemp, OilTemp |
| 0x200 | VEHICLE_STATUS | TCM | 50 ms | VehicleSpeed, BrakeSwitch |
| 0x201 | TRANSMISSION_STATUS | TCM | 100 ms | GearSelector, CurrentGear, TransTemp, TransFault, ShiftInProgress |
| 0x300 | BODY_STATUS | BCM | 200 ms | FuelLevel, Headlights, TurnIndicator, Door*Open (x4), SeatbeltFastened, BrakeLights |
| 0x400 | DASHBOARD_STATUS | IPC | 200 ms | Warn* lamps (x8), MasterSeverity, Odometer |
| 0x500 | DIAGNOSTIC_STATUS | DIAG | 1000 ms | EcmOnline, TcmOnline, BcmOnline, IpcOnline, ActiveDtcCount, LastDtc |

Vehicle speed comes from the TCM (transmission output-shaft sensor), which also
reads the brake switch for its shift logic. The BCM drives the brake lights.

## Signal scaling

`physical = raw * factor + offset`

| Signal | Bits | Factor | Offset | Range | Unit |
|---|---|---|---|---|---|
| EngineRPM | 16 | 0.25 | 0 | 0 – 16383.75 | rpm |
| EngineLoad, ThrottlePosition, FuelLevel | 8 | 0.5 | 0 | 0 – 100 | % |
| CoolantTemp, OilTemp, TransTemp | 8 | 1 | -40 | -40 – 215 | °C |
| VehicleSpeed | 16 | 0.01 | 0 | 0 – 300 | km/h |
| Odometer | 24 | 0.1 | 0 | 0 – 1677721.5 | km |

Enumerated signals:

- **EngineState**: OFF, STARTING, IDLE, ACCELERATING, CRUISING, DECELERATING, OVERHEAT, FAULT
- **GearSelector**: P, R, N, D (`CurrentGear` 1–6 is the engaged gear, 0 when none)
- **Headlights**: OFF, LOW, HIGH
- **TurnIndicator**: OFF, LEFT, RIGHT, HAZARD
- **MasterSeverity**: NONE, INFO, WARNING, CRITICAL

## End-to-end protection

Every message carries the same two protection signals, as production ECUs do:

| Signal | Location | Purpose |
|---|---|---|
| AliveCounter | byte 6, bits 0–3 | Increments 0–15 each transmission; a stuck or skipping counter means a frozen or lost sender |
| Checksum | byte 7 | `(sum(bytes 0–6) + ID & 0xFF + ID >> 8) mod 256, XOR 0xFF` |

Including the CAN ID in the checksum means a valid payload replayed under the
wrong ID is rejected.

## Decoding errors

The decoder never raises on bad traffic. It returns the frame tagged with one
of these errors, so the CAN monitor and diagnostics can report it:

| Error | Meaning |
|---|---|
| UNKNOWN_ID | ID not in the DBC (or an extended ID) |
| BAD_DLC | Payload length differs from the DBC |
| CHECKSUM | Checksum mismatch (signals are still decoded for display) |
| MALFORMED | cantools could not decode the payload |
| ERROR_FRAME | CAN error frame |

## Bus statistics

A passive monitor node (`backend/app/monitoring/bus_monitor.py`) listens on its
own bus instance and computes, over a sliding 1 s window of simulation time:

- messages per second, overall, per CAN ID and per sending ECU;
- **bus load** = bits on the wire per second / 500 kbit/s, where a standard
  data frame is `47 + 8 × DLC` bits (bit stuffing ignored). The full network is
  52 frames/s × 111 bits ≈ 5.8 kbit/s, about 1.2 % load;
- error counts by decode error type;
- **timeouts**: a message counts one timeout when it has been missing for more
  than 3 of its DBC cycle times, and clears when it is seen again;
- active nodes: ECUs heard within the window.

## Bus backends

| `CAN_MODE` | Behaviour |
|---|---|
| `auto` | SocketCAN on `CAN_CHANNEL` (default `vcan0`) if it opens, else the software bus |
| `socketcan` | SocketCAN only; startup fails if it is unavailable |
| `virtual` | python-can's in-process `virtual` interface |

Each ECU opens its own bus instance, like a physical node with its own
transceiver. On Linux, create `vcan0` with `scripts/setup_vcan.sh` (remove it
with `--remove`).
