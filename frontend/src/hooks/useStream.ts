import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { streamUrl } from "../services/api";

export type ConnectionState = "connecting" | "open" | "closed";

const MAX_RETRY_MS = 5000;

// Opens a WebSocket stream and reconnects with backoff, so restarting the
// backend never needs a page reload. `onMessage` may change between renders.
export function useStream<T>(
  path: "/ws/telemetry" | "/ws/can",
  onMessage: (message: T) => void,
  onDisconnect?: () => void,
): ConnectionState {
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const handlers = useRef({ onMessage, onDisconnect });
  useLayoutEffect(() => {
    handlers.current = { onMessage, onDisconnect };
  });

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let retryMs = 500;
    let disposed = false;

    const connect = () => {
      setConnection("connecting");
      socket = new WebSocket(streamUrl(path));
      socket.onopen = () => {
        retryMs = 500;
        setConnection("open");
      };
      socket.onmessage = (event) => handlers.current.onMessage(JSON.parse(event.data));
      socket.onclose = () => {
        if (disposed) return;
        setConnection("closed");
        handlers.current.onDisconnect?.();
        retryTimer = setTimeout(connect, retryMs);
        retryMs = Math.min(retryMs * 2, MAX_RETRY_MS);
      };
    };

    // Connect on the next tick: React's development double-mount runs the
    // cleanup synchronously, so the throwaway mount never opens a socket
    // (closing one mid-handshake makes the browser log a warning).
    retryTimer = setTimeout(connect, 0);
    return () => {
      disposed = true;
      clearTimeout(retryTimer);
      socket?.close();
    };
  }, [path]);

  return connection;
}
