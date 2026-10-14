import type { ClusterWarning, Severity } from "../types/api";
import { AlertOctagonIcon, AlertTriangleIcon, InfoIcon } from "./Icons";

const STYLE: Record<Severity, { color: string; border: string; Icon: typeof InfoIcon }> = {
  CRITICAL: {
    color: "var(--color-status-critical)",
    border: "border-status-critical/60",
    Icon: AlertOctagonIcon,
  },
  WARNING: {
    color: "var(--color-status-warning)",
    border: "border-status-warning/50",
    Icon: AlertTriangleIcon,
  },
  INFO: { color: "var(--color-accent)", border: "border-slate-700", Icon: InfoIcon },
};

interface WarningPanelProps {
  warnings: ClusterWarning[] | null;
}

// Active warnings, most severe first. Severity is carried by icon shape,
// colour and a text label, so it never relies on colour alone.
export default function WarningPanel({ warnings }: WarningPanelProps) {
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <h2 className="text-xs font-medium uppercase tracking-[0.15em] text-slate-400">Warnings</h2>
      {warnings === null ? (
        <p className="mt-3 text-sm text-slate-500">No data</p>
      ) : warnings.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">No active warnings</p>
      ) : (
        <ul className="mt-3 space-y-2" aria-live="polite">
          {warnings.map((w) => {
            const s = STYLE[w.severity];
            return (
              <li
                key={`${w.code}:${w.message}`}
                className={`flex items-center gap-3 rounded-md border bg-slate-950/60 px-3 py-2 ${s.border}`}
              >
                <s.Icon style={{ color: s.color }} />
                <span className="flex-1 text-sm text-slate-100">{w.message}</span>
                <span className="text-[11px] font-semibold tracking-wider text-slate-400">
                  {w.severity}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
