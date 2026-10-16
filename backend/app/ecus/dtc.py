"""Diagnostic trouble codes (OBD-II style).

On the bus a DTC travels as the standard 2-byte encoding: the top two bits
select the system (P powertrain, C chassis, B body, U network) and the
remaining 14 bits are the code digits read as hex, so P0217 is 0x0217 and
U0100 is 0xC100.
"""

from __future__ import annotations

_SYSTEMS = "PCBU"

DESCRIPTIONS = {
    "P0118": "Engine coolant temperature sensor circuit high (open circuit)",
    "P0217": "Engine coolant over-temperature condition",
    "P0218": "Transmission fluid over-temperature condition",
    "P0219": "Engine overspeed condition",
    "P2299": "Brake pedal / accelerator pedal position incompatible",
    "U0001": "High-speed CAN communication bus",
    "U0100": "Lost communication with ECM",
    "U0101": "Lost communication with TCM",
    "U0140": "Lost communication with BCM",
    "U0155": "Lost communication with instrument cluster",
    "U0401": "Invalid data received from ECM",
}


def encode(code: str) -> int:
    system = _SYSTEMS.index(code[0])
    return (system << 14) | (int(code[1:], 16) & 0x3FFF)


def decode(value: int) -> str:
    return f"{_SYSTEMS[(value >> 14) & 0x3]}{value & 0x3FFF:04X}"


def describe(code: str) -> str:
    return DESCRIPTIONS.get(code, "Unknown trouble code")
