# Development Guide

How to set up, change and extend the project.

## Setup

Prerequisites: Python 3.11+, Node.js 20.19+ (22 recommended), Git. Linux is
optional; you only need it for SocketCAN.

```bash
git clone https://github.com/Esammy-88/can-vehicle-dashboard.git
cd can-vehicle-dashboard

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

cd frontend && npm install && cd ..
```

Run the backend and frontend in two terminals:

```bash
uvicorn app.main:app --app-dir backend --reload --reload-dir backend
cd frontend && npm run dev         # http://localhost:5173
```

On Windows, `start-dev.cmd` opens both. The backend's interactive API docs
are at http://localhost:8000/docs.

### Configuration

Environment variables, read in `backend/app/config.py`:

| Variable | Default | Meaning |
|---|---|---|
| `CAN_MODE` | `auto` | `auto`, `socketcan` or `virtual` (see [can-protocol.md](can-protocol.md#bus-backends)) |
| `CAN_CHANNEL` | `vcan0` | SocketCAN interface |
| `LOG_DIR` | `logs` | Where event logs and CAN traces are written |
| `BACKEND_URL` | `http://127.0.0.1:8000` | Frontend dev server only: where `/api` and `/ws` are proxied |

### SocketCAN on Linux

```bash
./scripts/setup_vcan.sh            # create vcan0 (asks for sudo)
CAN_MODE=socketcan uvicorn app.main:app --app-dir backend
candump vcan0                      # from can-utils: watch the live traffic
./scripts/setup_vcan.sh --remove
```

## Before you commit

```bash
ruff format .
ruff check .
pytest
cd frontend && npm run build
```

CI runs the same checks and fails the build on any error.

## Conventions

- **The DBC is the source of truth.** Never hard-code an ID, scaling or cycle
  time in Python; read it from the codec (`codec.message(name)`).
- **ECUs talk only over CAN.** An ECU may read its own sensors and the driver
  inputs wired to it. Everything else it learns from frames. The instrument
  cluster and the dashboard show only decoded CAN data.
- **No wall-clock time in simulation code.** Use the `now` passed to `step()`.
  This keeps runs deterministic and tests instant.
- **Type hints everywhere** (Python) and **no `any`** (TypeScript).
- **Comments explain why**, such as an engineering decision or a real-world
  analogy, not what the next line does.
- **Tests assert on observable behaviour**: frames, the cluster's view, DTCs,
  events.
- Frontend status colours (green, amber, red) are reserved for status and
  always come with an icon or label, never colour alone.

## Common changes

### Add a signal to an existing message

1. Add the `SG_` line to `dbc/vehicle.dbc` in free bits of bytes 0–5. Bytes 6
   and 7 hold the alive counter and the checksum.
2. Return a value for it from the sender's `signals_for()` (encoding requires
   every signal).
3. Read it where it is needed, e.g. in `DashboardEcu.view()`, then in
   `frontend/src/types/api.ts` and the page that shows it.
4. Run `pytest`. `test_codec.py` samples every message, so a missing value
   fails straight away.

### Add a message

1. Add the `BO_` block with `AliveCounter` (bits 48–51) and `Checksum` (bits
   56–63), plus a `BA_ "GenMsgCycleTime"` line. The loader rejects the DBC
   otherwise.
2. Implement it in the sending ECU's `signals_for()`. The base class schedules
   it from the cycle time automatically.
3. Update `EXPECTED_MESSAGES` in `test_dbc.py`, the frame-rate figures in
   tests that count total traffic, and the message table in
   [can-protocol.md](can-protocol.md).

### Add an ECU

1. Subclass `Ecu` (`backend/app/ecus/base.py`). Set `node` to the DBC node
   name, implement `update(now)` (control logic) and `signals_for(name)`.
2. Create it in `Simulator.__init__` with its own `factory.open()` bus and add
   it to `self.ecus`. Order matters: receivers that should see this tick's
   frames go later.
3. If it should be supervised, add it to `WATCHED` and `LOST_COMM_DTC` in
   `ecus/diagnostics.py`.

### Add a fault

1. Add a `FaultType` and a `CATALOG` entry in `simulation/faults.py`.
2. Implement both directions in `FaultManager._apply()`: clearing must undo
   exactly what injecting did.
3. Act at the physical point of failure (plant, sensor, ECU power, bus), not
   on the detection side, so the network has to detect it on its own.
4. Add a test in `test_faults.py` (inject → detected → clear → recovered) and
   a row in [fault-injection.md](fault-injection.md). The frontend picks the
   new fault up from `GET /api/faults` without any change.

### Change the demo

The steps are data in `build_steps()` (`simulation/demo.py`). Each step has an
action on entry, a completion condition read from CAN, a hold time and a
timeout. `test_demo.py` fails if any step times out.

## Windows notes

- Run Python as `.venv\Scripts\python.exe` or activate the venv first.
- If PowerShell blocks `npm`, use `npm.cmd`, or run
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
- Quote paths that contain spaces: `cd "C:\path with spaces\can-vehicle-dashboard"`.
- SocketCAN is Linux-only. On Windows the backend uses the software bus, and
  for SocketCAN you can use WSL2 or a Linux VM.

## Commit messages

Use a short imperative subject line ("Add brake wear signal"), a blank line,
then what changed and why. Keep each commit focused on one change, and make
sure tests pass at every commit.
