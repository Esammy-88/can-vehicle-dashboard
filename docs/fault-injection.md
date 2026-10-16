# Fault Injection, Diagnostics and Logging

Faults are injected **where they would physically happen** — in the vehicle
plant, a sensor, an ECU or the bus — never by editing what the dashboard
shows. Detection therefore has to work the way it would in a real car: an ECU
notices something implausible, a node falls silent, or frames arrive corrupted.

Inject and clear faults from the **Fault injection** panel (Dashboard sidebar
or Diagnostics page) or the REST API (`POST /api/faults`,
`DELETE /api/faults/{type}`, `DELETE /api/faults` to clear all).

## Faults

| Fault | Injected as | Detected by | Result |
|---|---|---|---|
| Engine overheat | Cooling system failure in the plant: coolant heads ~45 °C above normal | ECM coolant check (≥ 112 °C, exit ≤ 105 °C) | Engine state OVERHEAT, torque limited to 50 % (limp mode), DTC **P0217**, cluster ENGINE OVERHEAT (critical) |
| Low fuel | Fuel leak, ~2 % of the tank per second | Cluster fuel rule (< 15 %) | LOW FUEL warning |
| Sensor failure | Coolant sensor open circuit: reads −40 °C | ECM plausibility check (valid range −35…200 °C) | DTC **P0118**, check-engine lamp; the ECM uses a substitute 90 °C so it does not raise a false overheat |
| ECU offline (ECM / TCM / BCM) | ECU powered down: stops receiving and sending | Watchdog: no frame for 1.5 s | ECU OFFLINE, DTC **U0100 / U0101 / U0140**, its values blank on the cluster. ECM offline also stalls the engine; on clear the ECU reboots and the engine restarts |
| CAN message timeout | One message stops being sent; its ECU keeps running | Bus monitor: missing for 3 cycles | MESSAGE_TIMEOUT, cluster *communication lost*; the ECU stays ONLINE if it still sends other messages (try ENGINE_TEMPERATURE) |
| Transmission overheat | Transmission oil cooler failure | TCM fluid temperature (≥ 120 °C, exit ≤ 110 °C) | TransFault, gears limited to 3rd (limp mode), DTC **P0218**, cluster TRANSMISSION FAULT |
| Stuck throttle | Accelerator pedal sensor stuck at ≥ 40 % | ECM brake-throttle override (brake + pedal ≥ 20 %) | The car keeps pulling when the pedal is released; braking cuts the throttle to 0 and sets DTC **P2299** |
| Invalid CAN messages | A rogue node sends 10 bad frames/s: corrupted ENGINE_STATUS (checksum), 4-byte VEHICLE_STATUS (DLC), unknown ID 0x6A5 | Every receiver's decoder; DIAG counts corrupted ECM frames | Frames rejected (values unaffected), error counters and red rows in the CAN monitor, DTC **U0401** |
| CAN bus interruption | Wiring fault: no frame reaches any node | Watchdog: every ECU silent | All ECUs OFFLINE, DTC **U0001**, cluster blank with communication-lost warnings |
| High RPM | Engine runs away past the rev limiter (~7200 rpm) | ECM overspeed (> 6500 rpm for 0.3 s), cluster RPM rule | DTC **P0219**, HIGH RPM warning |

## ECU timeout detection and watchdog

Every ECU proves it is alive through its periodic messages, each carrying a
rolling 0–15 **alive counter**. The diagnostic node (DIAG) runs a watchdog:

- no frame from an ECU for **1.5 s** → `ECU_TIMEOUT` with the timestamp, ECU,
  last received message and timeout, the ECU is shown OFFLINE and a U-code is
  set;
- the next frame from it → `ECU_ONLINE`, the U-code clears;
- an alive counter that repeats (a stuck sender) or jumps (lost frames) is
  counted as a counter error per ECU.

Message-level timeouts (3 missed cycles) are tracked separately by the bus
monitor, so the system can tell *"one message is missing"* from *"the ECU is
gone"*.

## Diagnostic trouble codes

ECUs broadcast their own active DTCs over CAN — the ECM in
`ENGINE_TEMPERATURE.EngineDtc` (rotating through all active codes, with
`EngineDtcCount`), the TCM in `TRANSMISSION_STATUS.TransDtc` — using the
standard 2-byte OBD-II encoding (P0217 → `0x0217`, U0100 → `0xC100`). DIAG
collects them, adds the network codes it detects itself, keeps a history with
set / cleared times, and broadcasts a summary in `DIAGNOSTIC_STATUS` (0x500).

| Code | Meaning | Raised by |
|---|---|---|
| P0118 | Engine coolant temperature sensor circuit high (open circuit) | ECM |
| P0217 | Engine coolant over-temperature condition | ECM |
| P0218 | Transmission fluid over-temperature condition | TCM |
| P0219 | Engine overspeed condition | ECM |
| P2299 | Brake pedal / accelerator pedal position incompatible | ECM |
| U0001 | High-speed CAN communication bus | DIAG |
| U0100 / U0101 / U0140 / U0155 | Lost communication with ECM / TCM / BCM / instrument cluster | DIAG |
| U0401 | Invalid data received from ECM | DIAG |

## Event log

Everything noteworthy is logged with wall-clock and simulation time, severity
(INFO / WARNING / CRITICAL), source and details: engine state changes (not the
constant accelerate / cruise / decelerate churn), selector changes, faults
injected and cleared, cluster warnings raised and cleared, DTCs set and
cleared, ECU timeouts and recoveries, message timeouts and restorations,
invalid frames (first one immediately, then a summary every 10 s), ECU
crashes and simulation resets.

Events are written as JSON lines to `logs/events-<timestamp>.jsonl`, shown on
the **Logs** page, and exportable as JSON or CSV
(`GET /api/logs/export?format=csv`). Set `LOG_DIR` to log elsewhere.

```json
{"seq": 41, "timestamp": "2026-10-16T04:01:58.345+00:00", "sim_time": 47.76,
 "severity": "CRITICAL", "event": "ECU_TIMEOUT", "source": "TCM",
 "message": "TRANSMISSION ECU OFFLINE: no frame for 1.5 s (last message TRANSMISSION_STATUS)",
 "details": {"ecu": "TCM", "last_message": "TRANSMISSION_STATUS", "last_seen_s": 46.26, "timeout_s": 1.5}}
```

## CAN traces

The Logs page can record every frame on the bus to
`logs/can-trace-<timestamp>.log` in candump log format:

```
(1792123318.345014) vcan0 300#8A0001000000066B R
(1792123318.376401) vcan0 200#052C0000000007C5 R
```

Read it back with python-can (`can.LogReader`), or on Linux replay it onto a
virtual interface with `canplayer -I can-trace-….log vcan0=vcan0` and watch it
with `candump vcan0` or Wireshark.
