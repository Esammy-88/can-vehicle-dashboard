import type { ReactNode } from "react";
import type { Cluster } from "../types/api";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  BrakeIcon,
  DoorIcon,
  EngineIcon,
  HighBeamIcon,
  LowBeamIcon,
  SeatbeltIcon,
  TemperatureIcon,
} from "./Icons";

interface LampProps {
  label: string;
  lit: boolean;
  color: string;
  blink?: boolean;
  children: ReactNode;
}

function Lamp({ label, lit, color, blink, children }: LampProps) {
  return (
    <div
      title={label}
      aria-label={`${label}: ${lit ? "on" : "off"}`}
      className={`flex h-9 w-9 items-center justify-center ${lit && blink ? "animate-blink" : ""}`}
      style={{ color: lit ? color : "#1e293b" }}
    >
      {children}
    </div>
  );
}

// Instrument-cluster telltale strip: function lamps in green/blue, warnings in
// amber/red. Each lamp has a tooltip and an accessible label.
export default function Telltales({ cluster }: { cluster: Cluster | null }) {
  const c = cluster;
  const indicator = c?.turn_indicator;
  const anyDoor = c ? Object.values(c.doors_open).some(Boolean) : false;
  const codes = new Set(c?.warnings.map((w) => w.code));
  const doorWarning = c?.warnings.find((w) => w.code === "DOOR_OPEN");
  const green = "var(--color-lamp-green)";
  const amber = "var(--color-status-warning)";
  const red = "var(--color-status-critical)";

  return (
    <div className="flex flex-wrap items-center justify-center gap-1">
      <Lamp label="Left indicator" lit={indicator === "LEFT" || indicator === "HAZARD"} color={green} blink>
        <ArrowLeftIcon />
      </Lamp>
      <Lamp label="Low beam" lit={c?.headlights === "LOW"} color={green}>
        <LowBeamIcon />
      </Lamp>
      <Lamp label="High beam" lit={c?.headlights === "HIGH"} color="var(--color-lamp-blue)">
        <HighBeamIcon />
      </Lamp>
      <Lamp label="Brake applied" lit={c?.brake === true} color={amber}>
        <BrakeIcon />
      </Lamp>
      <Lamp label="Door open" lit={anyDoor} color={doorWarning?.severity === "INFO" ? amber : red}>
        <DoorIcon />
      </Lamp>
      <Lamp label="Seatbelt" lit={codes.has("SEATBELT")} color={red}>
        <SeatbeltIcon />
      </Lamp>
      <Lamp label="Check engine" lit={codes.has("ENGINE_FAULT")} color={amber}>
        <EngineIcon />
      </Lamp>
      <Lamp label="Engine overheat" lit={codes.has("ENGINE_OVERHEAT")} color={red}>
        <TemperatureIcon />
      </Lamp>
      <Lamp label="Right indicator" lit={indicator === "RIGHT" || indicator === "HAZARD"} color={green} blink>
        <ArrowRightIcon />
      </Lamp>
    </div>
  );
}
