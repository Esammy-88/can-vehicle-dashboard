import { useEffect, useState } from "react";
import { telemetryUrl } from "../services/api";
import type { Snapshot } from "../types/api";

export type ConnectionState = "connecting" | "open" | "closed";

const MAX_RETRY_MS = 5000;

export interface Telemetry {
  connection: ConnectionState;
  snapshot: Snapshot | null;
}

// Subscribes to the backend's telemetry stream and reconnects with backoff,
// so restarting the backend never needs a page reload.
export function useTelemetry(): Telemetry {
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let retryMs = 500;
    let disposed = false;

    const connect = () => {
      setConnection("connecting");
      socket = new WebSocket(telemetryUrl());
      socket.onopen = () => {
        retryMs = 500;
        setConnection("open");
      };
      socket.onmessage = (event) => setSnapshot(JSON.parse(event.data));
      socket.onclose = () => {
        if (disposed) return;
        setConnection("closed");
        setSnapshot(null);
        retryTimer = setTimeout(connect, retryMs);
        retryMs = Math.min(retryMs * 2, MAX_RETRY_MS);
      };
    };

    connect();
    return () => {
      disposed = true;
      clearTimeout(retryTimer);
      socket?.close();
    };
  }, []);

  return { connection, snapshot };
}
