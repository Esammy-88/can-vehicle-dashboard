import { useEffect, useState } from "react";
import { fetchHealth } from "../services/api";
import type { HealthResponse } from "../types/api";

const POLL_INTERVAL_MS = 2000;

export interface BackendHealth {
  online: boolean;
  health: HealthResponse | null;
}

// Polls the REST health endpoint. Live telemetry will move to WebSockets in
// Phase 4; this only answers "is the backend reachable?".
export function useBackendHealth(): BackendHealth {
  const [state, setState] = useState<BackendHealth>({ online: false, health: null });

  useEffect(() => {
    let controller = new AbortController();

    const poll = async () => {
      controller.abort();
      controller = new AbortController();
      try {
        const health = await fetchHealth(controller.signal);
        setState({ online: true, health });
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          setState({ online: false, health: null });
        }
      }
    };

    poll();
    const timer = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      clearInterval(timer);
      controller.abort();
    };
  }, []);

  return state;
}
