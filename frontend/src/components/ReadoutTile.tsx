interface ReadoutTileProps {
  label: string;
  value: string;
  unit?: string;
}

// Placeholder numeric readout; replaced by automotive gauges in Phase 4.
export default function ReadoutTile({ label, value, unit }: ReadoutTileProps) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-5">
      <div className="font-mono text-xs uppercase tracking-widest text-slate-500">{label}</div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="font-mono text-4xl font-semibold text-slate-100 tabular-nums">
          {value}
        </span>
        {unit && <span className="font-mono text-sm text-slate-500">{unit}</span>}
      </div>
    </div>
  );
}
