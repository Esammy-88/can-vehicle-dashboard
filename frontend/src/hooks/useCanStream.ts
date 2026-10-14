import { useState } from "react";
import type { CanFrame, CanStats, CanStreamMessage } from "../types/api";
import { useStream, type ConnectionState } from "./useStream";

const MAX_FRAMES = 1000;

export interface CanStream {
  connection: ConnectionState;
  frames: CanFrame[];
  stats: CanStats | null;
}

// Decoded CAN traffic from the backend's bus monitor. Only mounted while the
// CAN monitor page is open, so the dashboard doesn't pay for it.
export function useCanStream(): CanStream {
  const [frames, setFrames] = useState<CanFrame[]>([]);
  const [stats, setStats] = useState<CanStats | null>(null);

  const connection = useStream<CanStreamMessage>(
    "/ws/can",
    (msg) => {
      setStats(msg.stats);
      if (msg.reset || msg.frames.length) {
        setFrames((prev) => (msg.reset ? msg.frames : [...prev, ...msg.frames]).slice(-MAX_FRAMES));
      }
    },
    () => setStats(null),
  );

  return { connection, frames, stats };
}
