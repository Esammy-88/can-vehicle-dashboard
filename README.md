# CAN Bus Vehicle Dashboard

A software-only automotive CAN bus simulation. Several simulated ECUs (Engine,
Transmission, Body, Instrument Cluster) exchange DBC-encoded CAN 2.0 frames over
a virtual bus, and a React dashboard visualises the traffic, vehicle state,
faults and diagnostics in real time. No physical hardware is required.

> **Status:** Phase 6 — faults and diagnostics. Live dashboard, CAN monitor,
> graphs, ten injectable faults, an ECU watchdog, diagnostic trouble codes, a
> diagnostics page and an event log. Demo mode comes next.

## Architecture

```
CAN Layer  →  ECU Layer  →  Vehicle Simulation  →  Monitoring  →  API / WebSocket  →  Frontend
(python-can,   (Engine,       (physics, sensors,     (watchdog,     (FastAPI)            (React,
 cantools)      TCU, BCM)      faults)                health, logs)                        Vite)
```

The CAN layer runs on Linux SocketCAN (`vcan0`) when available, and falls back
to an in-process software bus everywhere else (Windows, macOS, CI).

## Technologies

- **Backend:** Python 3.11+, FastAPI, Pydantic, python-can, cantools, pytest
- **Frontend:** React, TypeScript, Vite, Tailwind CSS

## Installation

Prerequisites: Python 3.11+, Node.js 20+.

```bash
# Backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# Frontend
cd frontend
npm install
```

## Running

**Windows, one click:** double-click `start-dev.cmd` in the project folder. It
opens the backend and the frontend in two separate windows (keep both open)
and then the dashboard in your browser.

Or start them yourself:

Start the backend (from the repository root):

```bash
uvicorn app.main:app --app-dir backend --reload --reload-dir backend
```

Start the frontend in a second terminal:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173. The dev server proxies `/api` and `/ws` to the
backend on port 8000 (set `BACKEND_URL` to use another backend address).

The simulation starts with the backend. To drive: turn the **ignition** on,
hold some **brake** and select **D** (the gearbox has a shift lock), release
the brake and add **throttle**.

To run the ECU network without a browser, printing values decoded from CAN:

```bash
python scripts/start_simulation.py          # scripted ~60 s drive in real time
python scripts/can_demo.py                  # a few frames, including bad ones
```

### API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Backend status, configured and resolved CAN backend |
| `GET /api/state` | Snapshot: cluster view, driver controls, simulation status |
| `POST /api/controls` | Partial update of driver inputs (ignition, throttle, brake, gear, lights, doors, seatbelt, indicators) |
| `POST /api/simulation/{start,pause,reset}` | Simulation control |
| `PUT /api/simulation/speed` | `{"factor": 0.5 \| 1 \| 2 \| 5}` |
| `GET /api/can/stats` | Bus statistics: rates per message / ECU, bus load, errors, timeouts, active nodes |
| `GET /api/can/frames?limit=N` | Most recent decoded frames |
| `GET /api/history?seconds=N` | Graph history (up to 300 s, sampled every 0.2 s) |
| `WS /ws/telemetry` | The snapshot pushed at 20 Hz, plus new history samples |
| `WS /ws/can` | New decoded frames and bus statistics every 100 ms |
| `GET /api/faults` | Fault catalogue and active faults |
| `POST /api/faults` | Inject `{"type": "ECU_OFFLINE", "target": "TCM"}` |
| `DELETE /api/faults/{type}` / `DELETE /api/faults` | Clear one fault / all faults |
| `GET /api/diagnostics` | ECU status (watchdog), active DTCs, DTC history |
| `GET /api/logs`, `GET /api/logs/export?format=json\|csv` | Event log and export |
| `POST /api/logs/trace` | `{"action": "start" \| "stop"}` CAN trace recording |
| `GET /api/logs/files[/{name}]` | List / download event logs and traces |

Interactive API docs are at http://localhost:8000/docs.

### CAN mode

| `CAN_MODE` | Behaviour |
|---|---|
| `auto` (default) | Use SocketCAN `vcan0` if present, otherwise the software bus |
| `socketcan` | Require SocketCAN (Linux / WSL2) |
| `virtual` | Always use the in-process software bus |

On Linux, create `vcan0` with `./scripts/setup_vcan.sh` (remove it with
`--remove`). Message IDs, signals and cycle times are documented in
[docs/can-protocol.md](docs/can-protocol.md); ECU behaviour and the physics
model are in [docs/ecu-design.md](docs/ecu-design.md).

## Testing

```bash
pytest
ruff check .
cd frontend && npm run build
```

## Dashboard

The dashboard renders what the **instrument cluster ECU** decoded from CAN,
never simulation internals: speed and RPM gauges, gear and engine state,
coolant / oil / transmission temperature and fuel meters, telltale lamps, and
a warning panel (INFO / WARNING / CRITICAL). If an ECU goes silent its values
blank out and a *CAN communication lost* warning appears.

The **CAN Monitor** tab is a software CAN analyser: a passive bus node decodes
every frame (time, ID, message, ECU, DLC, raw bytes, decoded signals, errors),
with filters by ID / ECU / message / errors and pause. Above it are bus
statistics: messages per second, measured rate per message against its DBC
cycle time, frames per ECU, bus load, error counts by type, timeouts and
active nodes.

The **Graphs** tab plots speed, RPM, coolant and oil temperature, fuel, engine
load and CAN message rate over a selectable 30 s – 5 min window.

The **fault injection** panel (on the Dashboard and Diagnostics pages) injects
ten faults where they would physically happen — engine and transmission
cooling failures, a fuel leak, a broken sensor, a stuck pedal, an ECU powering
off, a missing message, a rogue node sending invalid frames, a bus wiring
fault, an engine runaway — and the network has to detect them itself.

The **Diagnostics** tab shows each ECU's watchdog status (ONLINE / OFFLINE,
last frame, timeouts, alive-counter errors), the bus status, active OBD-II
trouble codes and the fault and DTC history. The **Logs** tab shows the event
log (also written to `logs/` as JSON lines, exportable as JSON or CSV) and
records raw CAN traces in candump format. Details in
[docs/fault-injection.md](docs/fault-injection.md).

## Screenshots

_Coming in Phase 8._

## Demo

_Coming in Phase 7._

## License

MIT — see [LICENSE](LICENSE).
