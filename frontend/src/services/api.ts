import type {
  ActiveFault,
  Controls,
  ControlsUpdate,
  DemoStatus,
  Diagnostics,
  FaultCatalogEntry,
  LogFile,
  SimulationStatus,
  SpeedFactor,
  TraceStatus,
} from "../types/api";

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

export function demoAction(action: "start" | "stop"): Promise<DemoStatus> {
  return send("POST", `/api/demo/${action}`);
}

export function streamUrl(path: "/ws/telemetry" | "/ws/can"): string {
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${window.location.host}${path}`;
}

export async function getFaultCatalog(): Promise<FaultCatalogEntry[]> {
  return (await send<{ catalog: FaultCatalogEntry[] }>("GET", "/api/faults")).catalog;
}

export function injectFault(type: string, target: string | null): Promise<ActiveFault[]> {
  return send("POST", "/api/faults", { type, target });
}

export function clearFault(type: string, target: string | null): Promise<ActiveFault[]> {
  const query = target ? `?target=${encodeURIComponent(target)}` : "";
  return send("DELETE", `/api/faults/${type}${query}`);
}

export function clearAllFaults(): Promise<ActiveFault[]> {
  return send("DELETE", "/api/faults");
}

export function clearDtcHistory(): Promise<Diagnostics> {
  return send("DELETE", "/api/diagnostics/dtcs");
}

export function getTraceStatus(): Promise<TraceStatus> {
  return send("GET", "/api/logs/trace");
}

export function controlTrace(action: "start" | "stop"): Promise<TraceStatus> {
  return send("POST", "/api/logs/trace", { action });
}

export function listLogFiles(): Promise<LogFile[]> {
  return send("GET", "/api/logs/files");
}
