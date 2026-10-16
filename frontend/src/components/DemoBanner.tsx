import { useState } from "react";
import { demoAction } from "../services/api";
import type { DemoStatus } from "../types/api";
import { formatSimTime } from "../utils/format";

const BUTTON = "shrink-0 rounded-md border border-slate-600 px-3 py-1 text-sm text-slate-200 hover:bg-slate-800";

function run(action: "start" | "stop") {
  demoAction(action).catch((error) => console.error(error));
}

/** One segment per step: done, current, upcoming. */
function StepTrack({ step, total, finished }: { step: number; total: number; finished: boolean }) {
  return (
    <div className="flex gap-1" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={step}>
      {Array.from({ length: total }, (_, i) => {
        const done = finished || i + 1 < step;
        const current = !finished && i + 1 === step;
        return (
          <span
            key={i}
            className={`h-1.5 w-4 rounded-full ${
              done ? "bg-[var(--color-accent)]" : current ? "animate-pulse bg-sky-300" : "bg-slate-700"
            }`}
          />
        );
      })}
    </div>
  );
}

// Shown on every page while Demo Mode runs, so the narration stays on screen
// whichever page the presenter is showing.
export default function DemoBanner({ demo }: { demo: DemoStatus | undefined }) {
  const [dismissed, setDismissed] = useState(false);
  if (demo?.active && dismissed) setDismissed(false); // a new run shows the banner again
  if (!demo || !(demo.active || demo.finished) || dismissed) return null;

  return (
    <div
      className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-sky-900/70 bg-slate-900 px-6 py-3"
      aria-live="polite"
    >
      <span className="shrink-0 rounded-full bg-[var(--color-accent)] px-2.5 py-0.5 text-xs font-bold tracking-[0.15em] text-slate-950">
        DEMO
      </span>
      {demo.active ? (
        <div className="min-w-0 flex-1">
          <div className="text-sm text-slate-400">
            Step {demo.step} of {demo.total} ·{" "}
            <span className="font-semibold text-slate-50">{demo.title}</span>
          </div>
          <div className="mt-0.5 text-base text-slate-200">{demo.caption}</div>
        </div>
      ) : (
        <div className="min-w-0 flex-1 text-sm text-slate-300">
          <span className="font-semibold text-slate-50">Demo complete</span> · all {demo.total} steps in{" "}
          {formatSimTime(demo.elapsed_s, 0)} of simulated time. The controls are yours again.
        </div>
      )}
      <StepTrack step={demo.step} total={demo.total} finished={demo.finished} />
      {demo.active ? (
        <button type="button" onClick={() => run("stop")} className={BUTTON}>
          Stop demo
        </button>
      ) : (
        <div className="flex gap-2">
          <button type="button" onClick={() => run("start")} className={BUTTON}>
            Run again
          </button>
          <button type="button" onClick={() => setDismissed(true)} className={BUTTON}>
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}
