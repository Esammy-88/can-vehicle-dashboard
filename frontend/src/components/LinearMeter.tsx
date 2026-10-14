import type { ReactNode } from "react";

export type Tone = "normal" | "warning" | "critical";

const FILL: Record<Tone, string> = {
  normal: "var(--color-accent)",
  warning: "var(--color-status-warning)",
  critical: "var(--color-status-critical)",
};

const TRACK: Record<Tone, string> = {
  normal: "var(--color-accent-track)",
  warning: "#3d2c0a",
  critical: "#3d1414",
};

const TONE_LABEL: Record<Tone, string | null> = { normal: null, warning: "Warning", critical: "Critical" };

interface LinearMeterProps {
  label: string;
  icon: ReactNode;
  value: number | null;
  unit: string;
  min: number;
  max: number;
  tone: (value: number) => Tone;
  /** Scale positions to mark (e.g. warning thresholds). */
  marks?: number[];
  format?: (value: number) => string;
}

// A horizontal meter: the fill carries severity, the track is a dim step of
// the same hue so the state reads across the whole bar.
export default function LinearMeter({
  label,
  icon,
  value,
  unit,
  min,
  max,
  tone,
  marks = [],
  format = (v) => Math.round(v).toString(),
}: LinearMeterProps) {
  const t: Tone = value === null ? "normal" : tone(value);
  const fraction = value === null ? 0 : Math.min(Math.max((value - min) / (max - min), 0), 1);
  const state = TONE_LABEL[t];

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-slate-400">
          {icon}
          <span className="text-xs font-medium uppercase tracking-[0.15em]">{label}</span>
        </div>
        {state && (
          <span className="flex items-center gap-1.5 text-xs text-slate-300">
            <span className="h-2 w-2 rounded-full" style={{ background: FILL[t] }} />
            {state}
          </span>
        )}
      </div>
      <div className="mt-2 flex items-baseline gap-1.5">
        <span className="text-3xl font-semibold text-slate-50">
          {value === null ? "--" : format(value)}
        </span>
        <span className="text-sm text-slate-400">{unit}</span>
      </div>
      <div
        className="relative mt-3 h-2 rounded-full"
        style={{ background: TRACK[t] }}
        role="meter"
        aria-label={label}
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={value ?? undefined}
      >
        <div
          className="h-full rounded-full"
          style={{
            width: `${fraction * 100}%`,
            background: FILL[t],
            transition: "width 200ms linear",
          }}
        />
        {marks.map((m) => (
          <span
            key={m}
            className="absolute -top-1 h-4 w-px bg-slate-500"
            style={{ left: `${((m - min) / (max - min)) * 100}%` }}
          />
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-slate-600">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}
