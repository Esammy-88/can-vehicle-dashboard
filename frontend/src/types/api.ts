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

export interface ActiveFault {
  type: string;
  target: string | null;
  label: string;
  since: number;
}

export interface FaultCatalogEntry {
  type: string;
  label: string;
  description: string;
  targets: string[];
}

export interface EcuHealth {
  node: string;
  name: string;
  online: boolean;
  last_message: string | null;
  last_seen_ago_s: number | null;
  timeouts: number;
  counter_errors: number;
}

export interface DtcRecord {
  code: string;
  ecu: string;
  description: string;
  set_at: number;
  cleared_at: number | null;
}

export interface Diagnostics {
  ecus: EcuHealth[];
  last_frame_ago_s: number | null;
  active_dtcs: DtcRecord[];
  dtc_history: DtcRecord[];
}

export interface BusSummary {
  messages_per_s: number;
  errors: number;
  total_frames: number;
}

export interface Snapshot {
  simulation: SimulationStatus;
  can_backend: "socketcan" | "virtual";
  can_mode: "auto" | "socketcan" | "virtual";
  cluster: Cluster;
  controls: Controls;
  faults: ActiveFault[];
  diagnostics: Diagnostics;
  bus_down: boolean;
  bus: BusSummary;
}

export interface LogEvent {
  seq: number;
  timestamp: string;
  sim_time: number;
  severity: Severity;
  event: string;
  source: string;
  message: string;
  details: Record<string, unknown>;
}

export interface TraceStatus {
  recording: boolean;
  file: string | null;
  frames: number;
}

export interface LogFile {
  name: string;
  bytes: number;
}

export type ControlsUpdate = Partial<Omit<Controls, "doors_open">> & {
  doors_open?: Partial<Record<DoorName, boolean>>;
};

/** One graph sample, taken from the cluster view every 0.2 s of sim time. */
export interface HistorySample {
  seq: number;
  t: number;
  can_rate: number;
  speed_kmh: number | null;
  rpm: number | null;
  coolant_c: number | null;
  oil_c: number | null;
  fuel_pct: number | null;
  engine_load: number | null;
}

export interface TelemetryMessage extends Snapshot {
  samples: HistorySample[];
  events: LogEvent[];
  reset: boolean;
}

export type FrameError = "UNKNOWN_ID" | "BAD_DLC" | "CHECKSUM" | "MALFORMED" | "ERROR_FRAME";

export interface CanFrame {
  seq: number;
  t: number;
  id: number;
  name: string | null;
  sender: string;
  dlc: number;
  data: string;
  signals: Record<string, number | string>;
  error: FrameError | null;
  error_detail: string | null;
}

export interface IdStats {
  id: number;
  name: string | null;
  sender: string;
  cycle_ms: number | null;
  rate: number;
  count: number;
  errors: number;
  timeouts: number;
  timed_out: boolean;
  last_seen_ago_s: number | null;
}

export interface CanStats {
  messages_per_s: number;
  bus_load_pct: number;
  bitrate_bps: number;
  total_frames: number;
  errors: number;
  errors_by_type: Partial<Record<FrameError, number>>;
  timeouts: number;
  active_nodes: string[];
  per_ecu: { ecu: string; rate: number }[];
  per_id: IdStats[];
}

export interface CanStreamMessage {
  frames: CanFrame[];
  stats: CanStats;
  reset: boolean;
}
