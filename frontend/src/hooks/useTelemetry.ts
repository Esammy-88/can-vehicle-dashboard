import { useState } from "react";
import type { HistorySample, Snapshot, TelemetryMessage } from "../types/api";
import { useStream, type ConnectionState } from "./useStream";

export type { ConnectionState };

const MAX_SAMPLES = 1500; // 5 minutes at 5 Hz, matching the backend history

export interface Telemetry {
  connection: ConnectionState;
  snapshot: Snapshot | null;
  history: HistorySample[];
}

// Live cluster snapshot (20 Hz) plus the graph history. The backend sends the
// full history on connect and only new samples afterwards.
export function useTelemetry(): Telemetry {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [history, setHistory] = useState<HistorySample[]>([]);

  const connection = useStream<TelemetryMessage>(
    "/ws/telemetry",
    ({ samples, reset, ...snap }) => {
      setSnapshot(snap);
      if (reset || samples.length) {
        setHistory((prev) => (reset ? samples : [...prev, ...samples]).slice(-MAX_SAMPLES));
      }
    },
    () => setSnapshot(null),
  );

  return { connection, snapshot, history };
}
