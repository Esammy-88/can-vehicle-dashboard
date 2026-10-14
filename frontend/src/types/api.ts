// Shapes of the backend's REST and WebSocket payloads.

export type Severity = "INFO" | "WARNING" | "CRITICAL";
export type MasterSeverity = "NONE" | Severity;
export type Selector = "P" | "R" | "N" | "D";
export type Headlights = "OFF" | "LOW" | "HIGH";
export type TurnIndicator = "OFF" | "LEFT" | "RIGHT" | "HAZARD";
export type DoorName = "front_left" | "front_right" | "rear_left" | "rear_right";
export type EcuNode = "ECM" | "TCM" | "BCM";

export interface ClusterWarning {
  code: string;
  severity: Severity;
  message: string;
}

/** What the instrument cluster ECU decoded from CAN; null where data is missing. */
export interface Cluster {
  speed_kmh: number | null;
  brake: boolean | null;
  rpm: number | null;
  engine_load: number | null;
  throttle: number | null;
  engine_running: boolean | null;
  engine_state: string | null;
  coolant_c: number | null;
  oil_c: number | null;
  gear: string | null;
  selector: Selector | null;
  current_gear: number | null;
  trans_c: number | null;
  shift_in_progress: boolean | null;
  fuel_pct: number | null;
  headlights: Headlights | null;
  turn_indicator: TurnIndicator | null;
  brake_lights: boolean | null;
  seatbelt_fastened: boolean | null;
  doors_open: Record<DoorName, boolean | null>;
  odometer_km: number;
  warnings: ClusterWarning[];
  master_severity: MasterSeverity;
  sources_online: Record<EcuNode, boolean>;
}

/** The driver's inputs as the simulation currently has them. */
export interface Controls {
  ignition: boolean;
  throttle: number;
  brake: number;
  gear_selector: Selector;
  headlights: Headlights;
  turn_indicator: TurnIndicator;
  doors_open: Record<DoorName, boolean>;
  seatbelt_fastened: boolean;
}

export type SpeedFactor = 0.5 | 1 | 2 | 5;

export interface SimulationStatus {
  running: boolean;
  speed: SpeedFactor;
  time_s: number;
  crashed_ecus: string[];
}

export interface Snapshot {
  simulation: SimulationStatus;
  can_backend: "socketcan" | "virtual";
  can_mode: "auto" | "socketcan" | "virtual";
  cluster: Cluster;
  controls: Controls;
}

export type ControlsUpdate = Partial<Omit<Controls, "doors_open">> & {
  doors_open?: Partial<Record<DoorName, boolean>>;
};
