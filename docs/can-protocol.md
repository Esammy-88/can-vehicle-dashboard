# CAN Protocol

The network is described in [`dbc/vehicle.dbc`](../dbc/vehicle.dbc), which is
the single source of truth for IDs, signal layout, scaling and cycle times.
All frames are classic CAN 2.0A: standard 11-bit identifiers, 8-byte payload,
little-endian (Intel) signals.

## The CAN frame

A classic CAN data frame with an 11-bit identifier looks like this on the wire:

```
 SOF | Identifier | RTR | IDE | r0 | DLC  | Data       | CRC     | ACK | EOF
  1  |    11      |  1  |  1  |  1 |  4   | 0–64 bits  | 15 + 1  |  2  |  7    (bits)
```

| Field | Meaning | In this project |
|---|---|---|
| **Identifier (CAN ID)** | Names the *message*, not the sender. It also sets the priority: lower is more important | `0x100`–`0x500`, one per message |
| **RTR / IDE** | Remote request / extended (29-bit) ID flags | Always data frames with standard IDs |
| **DLC** | Data Length Code: payload length, 0–8 bytes | Always 8; any other length is reported as `BAD_DLC` |
| **Data (payload)** | Up to 8 bytes holding the *signals*, packed at bit positions given by the DBC | Signals, plus AliveCounter and Checksum in bytes 6–7 |
| **CRC, ACK, EOF** | Transmission checks done by the CAN controller hardware | Handled by the bus layer, so not modelled |

Header plus trailer come to 47 bits, so an 8-byte frame is
`47 + 8 × 8 = 111` bits before bit stuffing. That is the figure the bus-load
statistic uses.

CAN has no addresses. Every node receives every frame and decides from the ID
whether it cares. Which messages each ECU consumes is listed as the receivers
of each signal in the DBC.

## Arbitration

When several nodes start transmitting at the same moment, they resolve it bit
by bit while sending the identifier. A `0` bit is *dominant* and overrides a
`1`. A node that sends `1` but reads back `0` has lost: it stops and retries
after the frame. The lowest ID therefore always wins, and the winning frame is
not damaged (non-destructive arbitration). This is why IDs are allocated by
importance:

| Range | Use | Why |
|---|---|---|
| `0x1xx` | Engine | Powertrain control data, highest priority |
| `0x2xx` | Vehicle speed, transmission | Powertrain, consumed by the ECM and the cluster |
| `0x3xx` | Body | Comfort and lighting, can tolerate delay |
| `0x4xx` | Cluster status | Display only |
| `0x5xx` | Diagnostics | Lowest priority, 1 Hz summary |

The software bus delivers frames in the order they are sent. The simulator
steps the ECUs in node order (ECM, TCM, BCM, IPC, DIAG), so frames due in the
same tick go out in ID order, just as arbitration would order them on a real
bus. On `vcan0`, the kernel does the same.

## Message scheduling

Every message is **cyclic**: it is sent at a fixed period, its DBC
`GenMsgCycleTime`, whether or not its values changed. Receivers can then
detect a missing sender from silence alone (see
[fault-injection.md](fault-injection.md)). Each ECU keeps one transmit slot per
message it owns:

- On every 10 ms tick, a slot whose time has come encodes the current
  signals, increments its alive counter and sends the frame. Then
  `next_due += period`.
- Periods are counted in simulation time, so a 50 ms message is sent
  exactly every 5 ticks, with no drift and no jitter. Tests check measured
  rates against the DBC.
- If an ECU falls behind (paused, or rebooting after an `ECU_OFFLINE` fault),
  the slot resynchronises instead of sending a burst of catch-up frames.

| Period | Messages | Frames/s |
|---|---|---|
| 50 ms | VEHICLE_STATUS | 20 |
| 100 ms | ENGINE_STATUS, TRANSMISSION_STATUS | 10 + 10 |
| 200 ms | BODY_STATUS, DASHBOARD_STATUS | 5 + 5 |
| 500 ms | ENGINE_TEMPERATURE | 2 |
| 1000 ms | DIAGNOSTIC_STATUS | 1 |
| | **Total** | **53** |

The fast messages are the ones control loops depend on: speed for the ECM
and the cluster, RPM and throttle for the TCM's shift logic. Temperatures
change slowly, so 2 Hz is plenty.

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
| 0x101 | ENGINE_TEMPERATURE | ECM | 500 ms | CoolantTemp, OilTemp, EngineDtc, EngineDtcCount |
| 0x200 | VEHICLE_STATUS | TCM | 50 ms | VehicleSpeed, BrakeSwitch |
| 0x201 | TRANSMISSION_STATUS | TCM | 100 ms | GearSelector, CurrentGear, TransTemp, TransFault, ShiftInProgress, TransDtc |
| 0x300 | BODY_STATUS | BCM | 200 ms | FuelLevel, Headlights, TurnIndicator, Door*Open (x4), SeatbeltFastened, BrakeLights |
| 0x400 | DASHBOARD_STATUS | IPC | 200 ms | Warn* lamps (x8), MasterSeverity, Odometer |
| 0x500 | DIAGNOSTIC_STATUS | DIAG | 1000 ms | EcmOnline, TcmOnline, BcmOnline, IpcOnline, ActiveDtcCount, LastDtc |

Vehicle speed comes from the TCM (transmission output-shaft sensor), which also
reads the brake switch for its shift logic. The BCM drives the brake lights.

DTC signals (`EngineDtc`, `TransDtc`, `LastDtc`) carry OBD-II trouble codes in
the standard 2-byte encoding (P0217 → `0x0217`, U0100 → `0xC100`); see
[fault-injection.md](fault-injection.md).

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
  53 frames/s × 111 bits ≈ 5.9 kbit/s, about 1.2 % load;
- error counts by decode error type;
- **timeouts**: a message counts one timeout when no *valid* frame has arrived
  for more than 3 of its DBC cycle times, and clears when a valid one is seen
  again. Corrupted frames under the same ID count as errors but don't keep
  the message alive, so a rogue node can't mask a dead ECU;
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
