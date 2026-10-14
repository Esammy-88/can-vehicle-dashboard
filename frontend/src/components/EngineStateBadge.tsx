const STATUS: Record<string, { dot: string; label: string }> = {
  OFF: { dot: "bg-slate-600", label: "Off" },
  STARTING: { dot: "bg-status-warning", label: "Starting" },
  IDLE: { dot: "bg-status-good", label: "Idle" },
  ACCELERATING: { dot: "bg-status-good", label: "Accelerating" },
  CRUISING: { dot: "bg-status-good", label: "Cruising" },
  DECELERATING: { dot: "bg-status-good", label: "Decelerating" },
  OVERHEAT: { dot: "bg-status-critical", label: "Overheat" },
  FAULT: { dot: "bg-status-critical", label: "Fault" },
};

export default function EngineStateBadge({ state }: { state: string | null }) {
  const s = state ? STATUS[state] : undefined;
  return (
    <div className="flex flex-col items-center">
      <span className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">Engine</span>
      <span className="mt-1 flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900 px-3 py-1 text-sm text-slate-200">
        <span className={`h-2 w-2 rounded-full ${s?.dot ?? "bg-slate-700"}`} />
        {s?.label ?? "No data"}
      </span>
    </div>
  );
}
