"""The scripts in scripts/ must keep working as the code evolves."""

import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def run(*args: str) -> str:
    result = subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        env={**os.environ, "CAN_MODE": "virtual", "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_can_demo_script() -> None:
    out = run(str(SCRIPTS / "can_demo.py"))

    assert "ENGINE_STATUS" in out
    assert "ERR CHECKSUM" in out
    assert "ERR UNKNOWN_ID" in out


def test_start_simulation_script_fast() -> None:
    out = run(str(SCRIPTS / "start_simulation.py"), "--fast")

    assert "ACCELERATING" in out
    assert "VEHICLE_STATUS" in out and "20.0 /s" in out
