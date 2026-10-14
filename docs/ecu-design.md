# ECU Design

The simulation is a software-in-the-loop (SIL) setup: a **plant model** plays
the physical car, and the **ECUs** are the controllers. ECUs read the plant
only through sensors, command it only through actuators, and talk to each
other only over CAN.

```
          driver inputs (pedals, selector, switches)
                 │
   ┌─────────────┼──────────────────────────────┐
   │             ▼                              │
   │   ┌─────┐ ┌─────┐ ┌─────┐                  │
   │   │ ECM │ │ TCM │ │ BCM │   ECUs           │
   │   └──┬──┘ └──┬──┘ └──┬──┘                  │
   │      └───────┴───────┴──── CAN bus ─────── │ ── sniffer / dashboard
   │   sensors ▲     │ actuators                │
   │           │     ▼                          │
   │   ┌───────────────────────┐                │
   │   │  Vehicle plant model  │  physics       │
   │   └───────────────────────┘                │
   └────────────────────────────────────────────┘
```

## Scheduling

`Simulator.step()` advances simulated time by 10 ms. Each ECU then:

1. drains its own bus and stores the latest decoded signals per message,
2. runs its control logic,
3. transmits every message whose DBC cycle time has elapsed, with an
   incrementing alive counter and checksum.

The plant then integrates one step using the ECUs' actuator commands. Time
is simulated, so a run is fully reproducible for a given seed; real-time mode
simply calls `step()` every 10 ms of wall time (one tick costs ~0.1 ms).

A received message is considered **stale** after three missed cycles; ECUs
fall back to safe defaults (e.g. the ECM assumes 0 km/h without the TCM).

If an ECU raises an exception it is marked crashed and taken off the bus; the
rest of the network keeps running.

## Engine Control Module (ECM)

| | |
|---|---|
| Sensors | throttle pedal, crank speed (RPM), engine load, coolant and oil temperature |
| From CAN | vehicle speed (`VEHICLE_STATUS`, TCM) |
| Actuators | fuel enable, torque limit |
| Transmits | `ENGINE_STATUS` (100 ms), `ENGINE_TEMPERATURE` (500 ms) |

State machine:

```
OFF ──ignition──▶ STARTING ──rpm ≥ 700──▶ IDLE ⇄ ACCELERATING ⇄ CRUISING ⇄ DECELERATING
                     │                         │
                     └─no start in 3 s─▶ FAULT ◀─ stall (rpm < 300, e.g. no fuel)
coolant ≥ 112 °C ─▶ OVERHEAT (torque limited to 50 %) ─ coolant ≤ 105 °C ─▶ driving state
any state ──ignition off──▶ OFF          FAULT is latched until the ignition is cycled
```

Driving states come from smoothed vehicle acceleration (via CAN) and RPM
rate: ACCELERATING above +1.5 km/h/s, DECELERATING below −1.5 km/h/s or when
coasting off-throttle, IDLE when stationary, otherwise CRUISING.

## Transmission Control Module (TCM)

| | |
|---|---|
| Sensors | output shaft speed (vehicle speed), transmission temperature, brake switch |
| From CAN | throttle position and engine RPM (`ENGINE_STATUS`, ECM) |
| Actuators | engaged gear, parking pawl, shift-in-progress torque reduction |
| Transmits | `VEHICLE_STATUS` (50 ms), `TRANSMISSION_STATUS` (100 ms) |

- **Selector interlocks:** leaving P requires the brake; P and R are refused
  above 3 km/h.
- **Shift schedule:** upshift when the engine would exceed
  `2000 + 40 × throttle%` rpm in the current gear (or above 6200 rpm), downshift
  below `1200 + 25 × throttle%` rpm. Pressing harder raises both points, which
  gives kickdown.
- **Anti-hunting:** a shift only happens if the new gear lands at least 300 rpm
  inside the opposite threshold, with at least 0.8 s between shifts.
- No upshifts while braking; first gear is selected below 5 km/h.
- A shift takes 0.4 s, during which drive torque is reduced to 30 %.

## Body Control Module (BCM)

| | |
|---|---|
| Inputs | headlight switch, turn/hazard stalk, door switches, seatbelt buckle, brake pedal switch, fuel sender |
| Actuators | brake lights |
| Transmits | `BODY_STATUS` (200 ms) |

The fuel reading is noisy (slosh) and damped with a 2 s filter, like a real
fuel gauge.

## Instrument Panel Cluster (IPC, dashboard ECU)

| | |
|---|---|
| Inputs | none wired: everything comes from CAN |
| From CAN | all ECM, TCM and BCM messages |
| Transmits | `DASHBOARD_STATUS` (200 ms): warning lamps, master severity, odometer |

The IPC integrates its own odometer from received vehicle speed and evaluates
the warnings below. Its view is what the web dashboard displays (streamed over
`/ws/telemetry`), so the browser only ever sees data that crossed the bus.

| Warning | Condition | Severity |
|---|---|---|
| CAN_COMM_LOST | an ECU's messages missing for 3 cycles (after a 1 s start-up grace) | CRITICAL |
| ENGINE_FAULT | `EngineState` = FAULT | CRITICAL |
| ENGINE_OVERHEAT | `EngineState` = OVERHEAT or coolant ≥ 110 °C | CRITICAL |
| TRANSMISSION_FAULT | `TransFault` = 1 | CRITICAL |
| HIGH_OIL_TEMP | oil ≥ 130 °C | WARNING |
| LOW_FUEL | fuel < 15 % | WARNING |
| DOOR_OPEN | any door open | INFO stationary, WARNING above 5 km/h |
| SEATBELT | unbuckled with engine running | INFO stationary, WARNING above 10 km/h |

## Vehicle physics (simplified)

This is a **believable simplified model, not a validated vehicle model**:

- Point mass of 1500 kg; aerodynamic drag, rolling resistance, linear brakes
  (up to ~0.75 g). Brakes and rolling resistance can stop the car but never
  push it backwards.
- Engine torque from a full-load torque curve (peak 250 Nm at 4000 rpm) scaled
  by throttle, minus friction losses (which give engine braking).
- The torque converter is reduced to two modes: slipping below stall speed
  (passes drive torque plus idle creep), locked above it (engine speed follows
  wheel speed through the gear ratio).
- 6-speed gearbox (3.5 / 2.1 / 1.4 / 1.0 / 0.8 / 0.65, final drive 3.7).
- Temperatures are first-order lags toward load-dependent targets: coolant
  ~88 °C at idle up to ~102 °C at full load (thermostat), oil runs hotter,
  everything cools toward 20 °C ambient with the engine off.
- Fuel consumption scales with throttle and RPM and is sped up 10× so the
  gauge visibly moves in a short demo.

Sensors add small Gaussian noise from a seeded RNG, so values look live but
runs remain reproducible.
