import type { ReactNode } from "react";

interface StatTileProps {
  label: string;
  value: string;
  unit?: string;
  detail?: ReactNode;
}

export default function StatTile({ label, value, unit, detail }: StatTileProps) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-xs uppercase tracking-[0.15em] text-slate-500">{label}</div>
      <div className="mt-1.5 text-2xl font-semibold text-slate-50">
        {value}
        {unit && <span className="ml-1 text-sm font-normal text-slate-400">{unit}</span>}
      </div>
      {detail && <div className="mt-1 text-xs text-slate-500">{detail}</div>}
    </div>
  );
}
