import type { Controls, ControlsUpdate, SimulationStatus, SpeedFactor } from "../types/api";

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`${method} ${path} failed: HTTP ${response.status}`);
  }
  return response.json();
}

export function updateControls(update: ControlsUpdate): Promise<Controls> {
  return send("POST", "/api/controls", update);
}

export function simulationAction(action: "start" | "pause" | "reset"): Promise<SimulationStatus> {
  return send("POST", `/api/simulation/${action}`);
}

export function setSimulationSpeed(factor: SpeedFactor): Promise<SimulationStatus> {
  return send("PUT", "/api/simulation/speed", { factor });
}

export function streamUrl(path: "/ws/telemetry" | "/ws/can"): string {
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${window.location.host}${path}`;
}
