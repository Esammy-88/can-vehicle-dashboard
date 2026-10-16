import { memo, useEffect, useState } from "react";
import { controlTrace, getTraceStatus, listLogFiles } from "../services/api";
import type { LogEvent, LogFile, Severity, TraceStatus } from "../types/api";
import { formatSimTime } from "../utils/format";

const SEVERITY_DOT: Record<Severity, string> = {
  INFO: "bg-[var(--color-accent)]",
  WARNING: "bg-status-warning",
  CRITICAL: "bg-status-critical",
};
const MAX_ROWS = 500;
const BUTTON = "rounded-md border border-slate-600 px-3 py-1 text-sm text-slate-200 hover:bg-slate-800";

function TracePanel() {
  const [status, setStatus] = useState<TraceStatus | null>(null);
  const [files, setFiles] = useState<LogFile[]>([]);

  const refresh = () => {
    getTraceStatus().then(setStatus).catch(() => setStatus(null));
    listLogFiles().then(setFiles).catch(() => setFiles([]));
  };
  useEffect(refresh, []);
  useEffect(() => {
    if (!status?.recording) return;
    const timer = setInterval(() => getTraceStatus().then(setStatus).catch(() => undefined), 1000);
    return () => clearInterval(timer);
  }, [status?.recording]);

  const toggle = () =>
    controlTrace(status?.recording ? "stop" : "start")
      .then(() => refresh())
      .catch(console.error);

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <h2 className="text-xs font-medium uppercase tracking-[0.15em] text-slate-400">CAN trace</h2>
      <p className="mt-2 text-sm text-slate-400">
        Records every frame in candump log format (replay with <code className="font-mono">canplayer</code>, read with
        python-can).
      </p>
      <div className="mt-3 flex items-center gap-3">
        <button
          type="button"
          onClick={toggle}
          disabled={status === null}
          className={
            status?.recording
              ? "rounded-md bg-status-critical px-3 py-1 text-sm font-semibold text-white hover:brightness-110"
              : BUTTON
          }
        >
          {status?.recording ? "Stop recording" : "Start recording"}
        </button>
        {status?.recording && (
          <span className="flex items-center gap-2 text-sm text-slate-300">
            <span className="h-2 w-2 animate-pulse rounded-full bg-status-critical" aria-hidden="true" />
            {status.frames.toLocaleString()} frames
          </span>
        )}
      </div>
      <h3 className="mt-5 text-xs uppercase tracking-[0.15em] text-slate-500">Log files</h3>
      {files.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">No files yet</p>
      ) : (
        <ul className="mt-2 max-h-64 space-y-1 overflow-auto text-sm">
          {files.map((f) => (
            <li key={f.name} className="flex justify-between gap-3">
              <a
                href={`/api/logs/files/${encodeURIComponent(f.name)}`}
                download
                className="truncate font-mono text-xs text-sky-400 hover:underline"
              >
                {f.name}
              </a>
              <span className="shrink-0 text-xs text-slate-500">{(f.bytes / 1024).toFixed(1)} KB</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function LogsPage({ events }: { events: LogEvent[] }) {
  const [severity, setSeverity] = useState<Severity | "ALL">("ALL");
  const [query, setQuery] = useState("");

  const q = query.trim().toLowerCase();
  const filtered = events.filter(
    (e) =>
      (severity === "ALL" || e.severity === severity) &&
      (!q || `${e.event} ${e.source} ${e.message}`.toLowerCase().includes(q)),
  );
  const rows = filtered.slice(-MAX_ROWS).reverse();

  return (
    <div className="grid gap-6 p-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="mr-auto text-xs font-medium uppercase tracking-[0.15em] text-slate-400">
            Event log
            <span className="ml-3 normal-case tracking-normal text-slate-500">
              {filtered.length} of {events.length} events
            </span>
          </h2>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search events"
            aria-label="Search events"
            className="w-48 rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-slate-200 focus:border-sky-500 focus:outline-none"
          />
          <div className="flex rounded-md border border-slate-700 bg-slate-950 p-0.5">
            {(["ALL", "INFO", "WARNING", "CRITICAL"] as const).map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={severity === s}
                onClick={() => setSeverity(s)}
                className={`rounded px-2.5 py-1 text-xs font-medium ${
                  severity === s ? "bg-slate-700 text-slate-50" : "text-slate-400 hover:bg-slate-800"
                }`}
              >
                {s === "ALL" ? "All" : s.charAt(0) + s.slice(1).toLowerCase()}
              </button>
            ))}
          </div>
          <a href="/api/logs/export?format=json" download className={BUTTON}>
            Export JSON
          </a>
          <a href="/api/logs/export?format=csv" download className={BUTTON}>
            Export CSV
          </a>
        </div>

        <div className="mt-3 max-h-[640px] overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-slate-900">
              <tr className="text-left text-xs text-slate-500">
                <th className="py-1.5 pr-4 font-medium">Sim time</th>
                <th className="pr-4 font-medium">Severity</th>
                <th className="pr-4 font-medium">Event</th>
                <th className="pr-4 font-medium">Source</th>
                <th className="font-medium">Message</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => (
                <tr key={e.seq} className="border-t border-slate-800/80 align-top" title={e.timestamp}>
                  <td className="whitespace-nowrap py-1.5 pr-4 font-mono text-xs text-slate-400">
                    {formatSimTime(e.sim_time)}
                  </td>
                  <td className="whitespace-nowrap pr-4">
                    <span className="inline-flex items-center gap-1.5 text-xs text-slate-300">
                      <span className={`h-2 w-2 rounded-full ${SEVERITY_DOT[e.severity]}`} aria-hidden="true" />
                      {e.severity}
                    </span>
                  </td>
                  <td className="whitespace-nowrap pr-4 font-mono text-xs text-slate-200">{e.event}</td>
                  <td className="pr-4 text-slate-400">{e.source}</td>
                  <td className="text-slate-300">{e.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <p className="py-6 text-center text-sm text-slate-500">No events match.</p>}
        </div>
      </section>

      <aside>
        <TracePanel />
      </aside>
    </div>
  );
}

// Re-render only when new events arrive.
export default memo(LogsPage);
