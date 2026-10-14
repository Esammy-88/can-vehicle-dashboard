# CAN Bus Vehicle Dashboard

A software-only automotive CAN bus simulation. Several simulated ECUs (Engine,
Transmission, Body, Instrument Cluster) exchange DBC-encoded CAN 2.0 frames over
a virtual bus, and a React dashboard visualises the traffic, vehicle state,
faults and diagnostics in real time. No physical hardware is required.

> **Status:** Phase 4 — live dashboard. Engine, Transmission, Body and
> Instrument Cluster ECUs run over the CAN bus against a simplified vehicle
> physics model, and the web dashboard shows the cluster's view live and lets
> you drive the car. CAN monitor and graphs come next.

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
| `WS /ws/telemetry` | The same snapshot pushed at 20 Hz |

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

## Screenshots

_Coming in Phase 8._

## Demo

_Coming in Phase 7._

## License

MIT — see [LICENSE](LICENSE).
