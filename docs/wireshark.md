# Inspecting CAN Traffic with Wireshark

With the backend on Linux SocketCAN, every ECU frame crosses the kernel's
`vcan0` interface, so standard tools can watch it: Wireshark, `tshark`, and
`candump` from can-utils. On Windows and macOS the backend uses an in-process
software bus that external tools cannot see. Use the dashboard's CAN Monitor
there instead.

## 1. Prepare

```bash
sudo apt install wireshark can-utils
sudo usermod -aG wireshark "$USER"     # capture without root; log out and back in
./scripts/setup_vcan.sh                # creates and brings up vcan0
CAN_MODE=socketcan uvicorn app.main:app --app-dir backend
```

`CAN_MODE=socketcan` makes the backend refuse to start rather than silently
fall back to the software bus if `vcan0` is missing. Quick check that traffic
is flowing:

```bash
candump vcan0
#  vcan0  200   [8]  00 00 00 00 00 00 03 FA
#  vcan0  100   [8]  00 00 00 00 00 00 05 F9
```

## 2. Capture

1. Start Wireshark and double-click **vcan0** in the interface list. (From a
   terminal: `wireshark -i vcan0 -k`.)
2. Frames appear at about 53 per second. Each row is one CAN frame, with the
   protocol column showing **CAN**.
3. To have something interesting to look at, click **Run demo** on the
   dashboard, or inject a fault.
4. Stop with the red square, then **File → Save As** to keep a `.pcapng`.

Headless, with `tshark`:

```bash
tshark -i vcan0 -a duration:10 -w capture.pcapng   # record 10 s
tshark -r capture.pcapng                           # print it
```

## 3. Filter

Type these into the display filter bar:

| Filter | Shows |
|---|---|
| `can.id == 0x100` | ENGINE_STATUS only |
| `can.id >= 0x200 && can.id <= 0x2ff` | Everything the TCM sends |
| `can.id in {0x100 0x101}` | All ECM traffic |
| `!(can.id == 0x200)` | Hide the 20 Hz VEHICLE_STATUS flood |
| `can.len != 8` | Wrong-length frames (inject *Invalid CAN messages*) |
| `can.flags.err == 1` | CAN error frames |

The message IDs are listed in [can-protocol.md](can-protocol.md#messages).

## 4. Inspect IDs and data

Select a frame. The detail pane shows the **Identifier**, the
**Extend/RTR/Error flags** (all clear: standard data frames) and the
**Frame-Length** (DLC, always 8 here). The bytes pane shows the 8 payload
bytes.

Wireshark does not read DBC files, so it shows raw bytes, not signals. To
decode one by hand, take ENGINE_STATUS `0x100` with data
`20 1C 64 64 0B 00 07 E8`:

| Bytes | Signal | Raw (little-endian) | × factor + offset | Value |
|---|---|---|---|---|
| 0–1 | EngineRPM | `0x1C20` = 7200 | × 0.25 | 1800 rpm |
| 2 | EngineLoad | `0x64` = 100 | × 0.5 | 50 % |
| 3 | ThrottlePosition | `0x64` = 100 | × 0.5 | 50 % |
| 4, bit 0 | EngineRunning | 1 | | running |
| 4, bits 1–3 | EngineState | `0x0B >> 1` = 5 | enum | DECELERATING |
| 6, bits 0–3 | AliveCounter | 7 | | 7 |
| 7 | Checksum | `0xE8` | | see below |

The checksum is
`(sum(bytes 0–6) + 0x00 + 0x01) mod 256 XOR 0xFF`, where `0x00` and `0x01` are
the low and high bytes of the ID `0x100`. Here bytes 0–6 sum to `0x116`, and
`0x116 + 0x00 + 0x01 = 0x117`. Its low byte is `0x17`, and `0x17 XOR 0xFF`
gives `0xE8`, which matches.
Watch the AliveCounter go 0, 1, 2 … 15, 0 on consecutive frames with the same
ID. The other signal positions are in `dbc/vehicle.dbc`.

For live *decoded* signals, use the dashboard's CAN Monitor, or decode with
cantools straight from the interface:

```bash
candump vcan0 | python -m cantools decode dbc/vehicle.dbc
```

## 5. Faults as they look on the wire

| Fault | What you see in Wireshark |
|---|---|
| ECU offline (TCM) | IDs `0x200` and `0x201` stop appearing |
| CAN message timeout | Only the chosen ID stops |
| Invalid CAN messages | ID `0x6A5` (not in the DBC), 4-byte `0x200` frames, `0x100` frames whose checksum doesn't match |
| CAN bus interruption | All traffic stops |
| Engine overheat | `0x101` byte 0 (coolant + 40) climbs past 152 (112 °C); its EngineDtc field reads `17 02` (P0217) |

## 6. Saved traces

The Logs page (or `POST /api/logs/trace`) records traces in candump log
format: `logs/can-trace-*.log`. These work on any platform, even when
recorded on the software bus. On Linux you can replay a trace onto `vcan0`
and watch it in Wireshark:

```bash
canplayer -I logs/can-trace-20261016-120000.log
```

Each frame goes to the interface named in the file (`vcan0`). Add
`vcan0=vcan0` style mappings to redirect it elsewhere. To read a trace from
Python, use `can.LogReader("logs/can-trace-....log")`.
