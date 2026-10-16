import { useEffect, useState } from "react";
import { clearAllFaults, clearFault, getFaultCatalog, injectFault } from "../services/api";
import type { ActiveFault, FaultCatalogEntry } from "../types/api";

function report(promise: Promise<unknown>) {
  promise.catch((error) => console.error(error));
}

interface FaultRowProps {
  fault: FaultCatalogEntry;
  active: ActiveFault[];
}

function FaultRow({ fault, active }: FaultRowProps) {
  const [target, setTarget] = useState(fault.targets[0] ?? null);
  const instance = active.find((a) => a.type === fault.type && a.target === target);
  const otherTargets = active.filter((a) => a.type === fault.type && a.target !== target);

  return (
    <li className="flex items-center gap-2 py-1.5">
      <span
        className={`h-2 w-2 shrink-0 rounded-full ${instance ? "bg-status-critical" : "bg-slate-700"}`}
        aria-hidden="true"
      />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm text-slate-200" title={fault.description}>
          {fault.label}
        </div>
        {otherTargets.length > 0 && (
          <div className="truncate text-[11px] text-slate-500">
            also active: {otherTargets.map((a) => a.target).join(", ")}
          </div>
        )}
      </div>
      {fault.targets.length > 0 && (
        <select
          value={target ?? ""}
          onChange={(e) => setTarget(e.target.value)}
          aria-label={`${fault.label} target`}
          className="max-w-36 rounded border border-slate-700 bg-slate-950 px-1.5 py-0.5 text-xs text-slate-300"
        >
          {fault.targets.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
      )}
      <button
        type="button"
        onClick={() => report(instance ? clearFault(fault.type, target) : injectFault(fault.type, target))}
        aria-pressed={Boolean(instance)}
        className={`w-16 shrink-0 rounded-md py-1 text-xs font-semibold transition-colors ${
          instance
            ? "bg-status-critical text-white hover:brightness-110"
            : "border border-slate-600 text-slate-200 hover:bg-slate-800"
        }`}
      >
        {instance ? "Clear" : "Inject"}
      </button>
    </li>
  );
}

// Fault injection: every fault from the backend catalogue, with a target
// picker for the ones that apply to a single ECU or message.
export default function FaultPanel({ active }: { active: ActiveFault[] | null }) {
  const [catalog, setCatalog] = useState<FaultCatalogEntry[] | null>(null);
  const connected = active !== null;

  useEffect(() => {
    if (!connected) return;
    getFaultCatalog()
      .then(setCatalog)
      .catch(() => setCatalog(null));
  }, [connected]); // fetched once per backend connection

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-medium uppercase tracking-[0.15em] text-slate-400">
          Fault injection
        </h2>
        <button
          type="button"
          disabled={!active?.length}
          onClick={() => report(clearAllFaults())}
          className="rounded-md border border-slate-600 px-2.5 py-0.5 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-40"
        >
          Clear all
        </button>
      </div>
      {catalog === null || active === null ? (
        <p className="mt-3 text-sm text-slate-500">Waiting for the backend…</p>
      ) : (
        <ul className="mt-2 divide-y divide-slate-800/80">
          {catalog.map((fault) => (
            <FaultRow key={fault.type} fault={fault} active={active} />
          ))}
        </ul>
      )}
    </section>
  );
}
