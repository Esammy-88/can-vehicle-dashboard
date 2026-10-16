# Demo Mode

Demo Mode runs a scripted drive that shows every part of the system, from a
cold start to a fault being detected and repaired, with no input from you. It
is meant for recording the project demonstration video.

## Running it

- **Dashboard:** *Simulation → Demo Mode → Run demo*.
- **API:** `POST /api/demo/start`, `POST /api/demo/stop`, `GET /api/demo`.
- **Terminal, no browser:** `python scripts/start_simulation.py --demo`
  (add `--fast` to skip real-time waiting).

Starting a demo resets the simulation, so every run is the same. A banner on
every page shows the current step, a one-line caption explaining what to look
at, and progress through the steps. You can switch pages while it runs.

While the demo runs, the driver controls and the fault panel are locked: the
API answers `409 Conflict` to `POST /api/controls` and to fault injection. Pause,
simulation speed, page navigation and the CAN trace still work. *Stop demo*
clears the faults it injected and gives the controls back. *Reset* also ends
the demo.

## The sequence

The sequence takes about 110 s of simulated time: just under 2 minutes at 1×,
or under a minute at 2×.

| # | Step | What happens | Moves on when |
|---|---|---|---|
| 1 | Start vehicle | Ignition on; engine OFF → STARTING → IDLE | The cluster shows IDLE (+3 s) |
| 2 | Select Drive | Brake pressed (shift lock), selector to D | TCM reports D |
| 3 | Accelerate | Throttle 60 % | 40 km/h |
| 4 | Gear changes | Upshifts 1 → 4 | 4th gear and 90 km/h |
| 5 | Speed increases | Throttle 80 %; load and coolant rise | 120 km/h |
| 6 | Cruise | Throttle 38 %, steady speed | ECM reports CRUISING (+6 s) |
| 7 | Brake | Throttle off, brake 35 %, brake lights | Stopped |
| 8 | Vehicle stopped | Selector to P, engine idles | TCM reports P (+3 s) |
| 9 | Inject a fault | **Engine overheat** (cooling system failure) | *Engine overheat* warning |
| 10 | Fault detected | ECM enters OVERHEAT limp mode, DTC **P0217** | P0217 active (+5 s) |
| 11 | ECU communication interrupted | **TCM offline**: it stops sending frames | *CAN communication lost* (+1 s) |
| 12 | ECU timeout reported | Watchdog: TCM OFFLINE after 1.5 s, DTC **U0101** | U0101 active (+5 s) |
| 13 | Communication recovers | TCM reboots and is back on the bus | TCM ONLINE, U0101 cleared (+3 s) |
| 14 | Fault clears | Cooling repaired; coolant falls | OVERHEAT and P0217 cleared (+3 s) |

"+N s" means the step stays on screen that long after its condition is met,
so the viewer can see the result.

## How it works

`backend/app/simulation/demo.py` holds the director. It acts only as the
driver and the test engineer would: it sets pedals and the selector, and
injects and clears faults through the same `FaultManager` the fault panel
uses. It never writes to the vehicle model or the ECUs.

Each step moves on when a condition is met, and every condition is read from
what the **instrument cluster decoded from CAN** (speed, gear, engine state,
warnings) or from the diagnostic node's DTCs. Because steps wait for
conditions rather than fixed timers, the sequence stays in step at any
simulation speed. A step that doesn't complete within its timeout is logged
as `DEMO_STEP_TIMEOUT` and the demo moves on, so it can never hang.

Every step is written to the event log (`DEMO_START`, `DEMO_STEP`,
`DEMO_COMPLETE` / `DEMO_STOPPED`, source `DEMO`), next to the events the
system raised. After a run, the Logs page shows each action followed by the
system's reaction.

## Recording the video

1. Start the app (`start-dev.cmd` on Windows, or the two commands in the
   README) and open http://localhost:5173 full screen (F11).
2. Optional: on the Logs page, *Start recording* a CAN trace to show
   afterwards.
3. Start the screen recorder (Xbox Game Bar `Win+Alt+R`, or OBS), then click
   **Run demo**.
4. Suggested tour while it runs:
   - **Dashboard** for steps 1–8: gauges, gear changes, coolant rising.
   - **CAN Monitor** briefly during the cruise, to show live frames.
   - **Dashboard** for steps 9–10: the overheat warning and the OVERHEAT
     badge.
   - **Diagnostics** for steps 11–13: TCM OFFLINE, U0101, then ONLINE again.
   - **Logs** at the end: the whole story in order.
5. Use **Pause** at any moment to talk over a frame, and **2×** to shorten the
   slow parts (the overheat build-up in step 9, the cool-down in step 14).
