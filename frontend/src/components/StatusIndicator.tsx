import type { ConnectionState } from "../hooks/useTelemetry";

const STYLE: Record<ConnectionState, { dot: string; text: string; label: string }> = {
  open: { dot: "bg-status-good", text: "text-slate-200", label: "Live" },
  connecting: { dot: "bg-status-warning", text: "text-slate-300", label: "Connecting" },
  closed: { dot: "bg-status-critical", text: "text-slate-300", label: "Offline" },
};

export default function StatusIndicator({ state }: { state: ConnectionState }) {
  const s = STYLE[state];
  return (
    <div className="flex items-center gap-2 text-xs uppercase tracking-wider">
      <span className={`h-2.5 w-2.5 rounded-full ${s.dot}`} />
      <span className="text-slate-500">Backend</span>
      <span className={s.text}>{s.label}</span>
    </div>
  );
}
