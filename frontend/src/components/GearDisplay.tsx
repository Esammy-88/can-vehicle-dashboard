import type { Cluster, Selector } from "../types/api";

const POSITIONS: Selector[] = ["P", "R", "N", "D"];

export default function GearDisplay({ cluster }: { cluster: Cluster | null }) {
  const selector = cluster?.selector ?? null;
  const gear = cluster?.current_gear;

  return (
    <div className="flex flex-col items-center">
      <span className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">Gear</span>
      <div className="mt-1 flex h-20 items-baseline">
        <span className="text-7xl font-semibold text-slate-50">{selector ?? "-"}</span>
        {selector === "D" && gear ? (
          <span className="ml-1 text-4xl font-semibold text-slate-300">{gear}</span>
        ) : null}
      </div>
      <div className="mt-2 flex gap-3 text-sm font-semibold">
        {POSITIONS.map((p) => (
          <span key={p} className={p === selector ? "text-slate-50" : "text-slate-600"}>
            {p}
          </span>
        ))}
      </div>
      <span
        className={`mt-2 text-[11px] uppercase tracking-[0.2em] ${
          cluster?.shift_in_progress ? "text-accent" : "text-transparent"
        }`}
      >
        Shifting
      </span>
    </div>
  );
}
