import { useState } from "react";
import type { HistorySample, LogEvent, Snapshot, TelemetryMessage } from "../types/api";
import { useStream, type ConnectionState } from "./useStream";

export type { ConnectionState };

const MAX_SAMPLES = 1500; // 5 minutes at 5 Hz, matching the backend history
const MAX_EVENTS = 2000;

export interface Telemetry {
  connection: ConnectionState;
  snapshot: Snapshot | null;
  history: HistorySample[];
  events: LogEvent[];
}

// Live cluster snapshot (20 Hz) plus the graph history. The backend sends the
// full history on connect and only new samples afterwards.
export function useTelemetry(): Telemetry {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [history, setHistory] = useState<HistorySample[]>([]);
  const [events, setEvents] = useState<LogEvent[]>([]);

  const connection = useStream<TelemetryMessage>(
    "/ws/telemetry",
    ({ samples, events: newEvents, reset, ...snap }) => {
      setSnapshot(snap);
      if (newEvents.length) {
        // Events outlive simulation resets; drop any we already have after a reconnect.
        setEvents((prev) => {
          const last = prev.length ? prev[prev.length - 1].seq : 0;
          return [...prev, ...newEvents.filter((e) => e.seq > last)].slice(-MAX_EVENTS);
        });
      }
      if (reset || samples.length) {
        setHistory((prev) => (reset ? samples : [...prev, ...samples]).slice(-MAX_SAMPLES));
      }
    },
    () => {
      // A restarted backend numbers events from 1 again; it re-sends its backlog on connect.
      setSnapshot(null);
      setEvents([]);
    },
  );

  return { connection, snapshot, history, events };
}
