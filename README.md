# CAN Bus Vehicle Dashboard

A software-only automotive CAN bus simulation. Several simulated ECUs (Engine,
Transmission, Body, Instrument Cluster) exchange DBC-encoded CAN 2.0 frames over
a virtual bus, and a React dashboard visualises the traffic, vehicle state,
faults and diagnostics in real time. No physical hardware is required.

> **Status:** Phase 2 — CAN layer. The DBC network definition, DBC-driven
> encoding/decoding (with alive counter and checksum) and the SocketCAN /
> software bus abstraction are done and tested. ECUs and the simulation come next.

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
uvicorn app.main:app --app-dir backend --reload
```

Start the frontend in a second terminal:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173. The dev server proxies `/api` and `/ws` to the
backend on port 8000.

### CAN mode

| `CAN_MODE` | Behaviour |
|---|---|
| `auto` (default) | Use SocketCAN `vcan0` if present, otherwise the software bus |
| `socketcan` | Require SocketCAN (Linux / WSL2) |
| `virtual` | Always use the in-process software bus |

On Linux, create `vcan0` with `./scripts/setup_vcan.sh` (remove it with
`--remove`). Message IDs, signals and cycle times are documented in
[docs/can-protocol.md](docs/can-protocol.md).

## Testing

```bash
pytest
ruff check .
cd frontend && npm run build
```

## Screenshots

_Coming in Phase 8._

## Demo

_Coming in Phase 7._

## License

MIT — see [LICENSE](LICENSE).
