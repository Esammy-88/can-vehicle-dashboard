# Testing

```bash
pytest                    # 172 tests, about 1 minute
ruff check .              # lint
ruff format --check .     # formatting
cd frontend && npm run build   # strict TypeScript type-check + production build
```

CI runs all of these on every push and pull request
([.github/workflows/ci.yml](../.github/workflows/ci.yml)), on Python 3.11 to
3.14. A separate job creates a real `vcan0` and runs the SocketCAN tests and
the full demo over it.

## Strategy

The simulator steps in **simulated time** (10 ms ticks) and every source of
randomness is seeded. Most tests therefore drive the network directly with
`sim.run_for(seconds)`: a 2-minute drive runs in a fraction of a second, and
the same inputs always give the same result. Nothing sleeps, and nothing
depends on the machine's speed.

Each test gets its own virtual CAN channel (`conftest.py` gives it a random
name), so tests never see each other's frames and could run in parallel.

The tests follow the layers of the system:

| Level | Files | What they prove |
|---|---|---|
| **Protocol** | `test_dbc.py`, `test_codec.py` | The DBC matches the spec (IDs, senders, cycle times) and the loader rejects any convention violation. Encode/decode round-trips, byte layout, scaling, range checks, alive counter wrap, checksum (including a payload replayed under the wrong ID), and every decode error type. |
| **Bus** | `test_bus.py`, `test_socketcan.py` | Backend selection (auto / socketcan / virtual) and frames travelling between separate nodes. On Linux with `vcan0`, the same over real kernel sockets, including the whole network. |
| **Plant** | `test_physics.py` | Torque curve, gearing, drag, brakes and park hold, reverse, warm-up and cool-down, fuel use and running dry, sensor behaviour at standstill. |
| **ECUs** | `test_engine_ecu.py`, `test_transmission_ecu.py`, `test_dashboard_ecu.py`, `test_diagnostics.py` | Each controller in isolation with frames injected on the bus: engine state machine, overheat limp mode, drive-by-wire brake override, shift schedule and interlock, warning rules, watchdog timeouts, alive-counter errors, DTC set and clear. |
| **Network** | `test_simulation.py`, `test_bus_monitor.py`, `test_history.py` | ECUs working together over CAN: a full drive, measured message rates against the DBC, bus load, timeouts, an ECU crash being contained. |
| **Faults** | `test_faults.py` | One test per fault: inject it, check the network detects it the way a car would (warning, DTC, watchdog), clear it, check recovery. |
| **Demo** | `test_demo.py` | The whole Demo Mode sequence runs in order with no step timing out, the system ends healthy, and stopping undoes the demo's faults. |
| **Runtime and API** | `test_runtime.py`, `test_api.py` | Real-time pacing, pause, reset and speed; every REST endpoint; both WebSocket streams, including the incremental and reset behaviour; Demo Mode locking manual controls (HTTP 409); log export and path-safe file download. |
| **Scripts** | `test_scripts.py` | The command-line scripts in `scripts/` run and print what the README says they do. |

Tests assert on what an observer **on the bus** would see (decoded frames, the
cluster's view, DTCs) wherever possible, rather than on internal fields. That
keeps them valid when internals are refactored, and it is the same rule the
dashboard follows.

## Coverage

Line coverage of `backend/app` is about 98 %. To measure it:

```bash
pip install coverage
coverage run --source=backend/app -m pytest
coverage report
```

On Windows and macOS, the uncovered lines are mostly the real SocketCAN
probe in `can/bus.py`; the Linux CI job covers it.

## SocketCAN tests

`backend/tests/test_socketcan.py` is skipped unless `vcan0` can be opened.
To run it on Linux:

```bash
./scripts/setup_vcan.sh
pytest -rs backend/tests/test_socketcan.py
```

Nothing else, such as a running backend, should be sending on `vcan0` at the
time. Set `CAN_TEST_CHANNEL` to use another interface. With
`CAN_TEST_REQUIRED=1` (as CI sets it), a missing interface fails the run
instead of skipping.

## Frontend

The frontend has no unit tests. It is a thin view over the backend's JSON: it
holds no simulation logic, every value it shows is computed and tested in the
backend, and the API payloads are typed in `src/types/api.ts`. It is checked
by:

- the strict TypeScript compiler in `npm run build`, run in CI;
- visual checks of every page at 1366 × 768, the target laptop screen, with
  the backend running (screenshots in [`../screenshots`](../screenshots)).

## Manual end-to-end check

1. Start the backend and frontend (README, *Running*).
2. Dashboard: **Run demo** and watch all 14 steps complete.
3. CAN Monitor: frames scroll and measured rates match the DBC.
4. Diagnostics: inject *ECU offline (TCM)*. Within 1.5 s the TCM shows
   OFFLINE and U0101 is active. Clear it and the TCM is ONLINE again.
5. Logs: export CSV, record a short CAN trace and download it.
