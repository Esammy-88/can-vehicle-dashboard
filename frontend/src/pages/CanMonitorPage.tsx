import { useState } from "react";
import StatTile from "../components/StatTile";
import { useCanStream } from "../hooks/useCanStream";
import type { CanFrame, CanStats, IdStats } from "../types/api";
import { formatSimTime, formatValue, hexId } from "../utils/format";

const MAX_ROWS = 200;
const PROTECTION_SIGNALS = new Set(["AliveCounter", "Checksum"]);

function Badge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-slate-300">
      <span
        className={`h-2 w-2 rounded-full ${ok ? "bg-status-good" : "bg-status-critical"}`}
        aria-hidden="true"
      />
      {label}
    </span>
  );
}

function StatsTiles({ stats }: { stats: CanStats }) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
      <StatTile label="Messages" value={stats.messages_per_s.toFixed(0)} unit="/s" />
      <StatTile
        label="Bus load"
        value={stats.bus_load_pct.toFixed(2)}
        unit="%"
        detail={`of ${stats.bitrate_bps / 1000} kbit/s`}
      />
      <StatTile
        label="Active nodes"
        value={stats.active_nodes.length.toString()}
        detail={stats.active_nodes.join(" · ") || "none"}
      />
      <StatTile label="Total frames" value={stats.total_frames.toLocaleString()} />
      <StatTile
        label="Errors"
        value={stats.errors.toString()}
        detail={
          Object.entries(stats.errors_by_type)
            .map(([type, n]) => `${type} ${n}`)
            .join(" · ") || "none"
        }
      />
      <StatTile label="Timeouts" value={stats.timeouts.toString()} detail="message missing > 3 cycles" />
    </div>
  );
}

function PerIdTable({ rows }: { rows: IdStats[] }) {
  return (
    <section className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <h2 className="text-xs font-medium uppercase tracking-[0.15em] text-slate-400">Messages</h2>
      <table className="mt-3 w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-slate-500">
            <th className="py-1.5 pr-4 font-medium">ID</th>
            <th className="pr-4 font-medium">Message</th>
            <th className="pr-4 font-medium">ECU</th>
            <th className="pr-4 text-right font-medium">Cycle</th>
            <th className="pr-4 text-right font-medium">Expected</th>
            <th className="pr-4 text-right font-medium">Measured</th>
            <th className="pr-4 text-right font-medium">Count</th>
            <th className="pr-4 text-right font-medium">Errors</th>
            <th className="pr-4 text-right font-medium">Last seen</th>
            <th className="font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {rows.map((r) => {
            const expected = r.cycle_ms ? 1000 / r.cycle_ms : null;
            const never = r.count === 0;
            return (
              <tr key={r.id} className="border-t border-slate-800/80 text-slate-300">
                <td className="py-1.5 pr-4 font-mono text-slate-100">{hexId(r.id)}</td>
                <td className="pr-4">{r.name ?? "unknown"}</td>
                <td className="pr-4">{r.sender}</td>
                <td className="pr-4 text-right">{r.cycle_ms ? `${r.cycle_ms} ms` : "–"}</td>
                <td className="pr-4 text-right">{expected === null ? "–" : `${expected.toFixed(0)}/s`}</td>
                <td className="pr-4 text-right text-slate-100">{r.rate.toFixed(0)}/s</td>
                <td className="pr-4 text-right">{r.count.toLocaleString()}</td>
                <td className="pr-4 text-right">{r.errors}</td>
                <td className="pr-4 text-right">
                  {r.last_seen_ago_s === null ? "never" : `${(r.last_seen_ago_s * 1000).toFixed(0)} ms`}
                </td>
                <td>
                  {never ? (
                    <span className="text-xs text-slate-500">Not on bus</span>
                  ) : (
                    <Badge ok={!r.timed_out} label={r.timed_out ? "Timeout" : "OK"} />
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

function PerEcu({ stats }: { stats: CanStats }) {
  const max = Math.max(1, ...stats.per_ecu.map((e) => e.rate));
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <h2 className="text-xs font-medium uppercase tracking-[0.15em] text-slate-400">Frames per ECU</h2>
      <ul className="mt-3 space-y-3">
        {stats.per_ecu.map((e) => (
          <li key={e.ecu}>
            <div className="flex justify-between text-sm">
              <span className="text-slate-300">{e.ecu}</span>
              <span className="tabular-nums text-slate-100">{e.rate.toFixed(0)}/s</span>
            </div>
            <div className="mt-1 h-1.5 rounded-full bg-[var(--color-accent-track)]">
              <div
                className="h-full rounded-full bg-[var(--color-accent)]"
                style={{ width: `${(e.rate / max) * 100}%` }}
              />
            </div>
          </li>
        ))}
        {stats.per_ecu.length === 0 && <li className="text-sm text-slate-500">No traffic</li>}
      </ul>
    </section>
  );
}

function Signals({ signals }: { signals: CanFrame["signals"] }) {
  const entries = Object.entries(signals);
  return (
    <span className="text-xs leading-5">
      {entries.map(([name, value]) => (
        <span
          key={name}
          className={`mr-3 inline-block ${PROTECTION_SIGNALS.has(name) ? "text-slate-600" : "text-slate-300"}`}
        >
          <span className="text-slate-500">{name}</span>={formatValue(value)}
        </span>
      ))}
    </span>
  );
}

interface Filters {
  id: string;
  ecu: string;
  message: string;
  errorsOnly: boolean;
}

function matches(frame: CanFrame, f: Filters): boolean {
  if (f.errorsOnly && !frame.error) return false;
  if (f.ecu !== "ALL" && frame.sender !== f.ecu) return false;
  if (f.message !== "ALL" && frame.name !== f.message) return false;
  if (f.id.trim()) {
    const wanted = f.id.trim().toLowerCase().replace(/^0x/, "");
    if (!frame.id.toString(16).includes(wanted)) return false;
  }
  return true;
}

const SELECT =
  "rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-slate-200 focus:border-sky-500 focus:outline-none";

export default function CanMonitorPage() {
  const { connection, frames, stats } = useCanStream();
  const [frozen, setFrozen] = useState<CanFrame[] | null>(null);
  const [filters, setFilters] = useState<Filters>({ id: "", ecu: "ALL", message: "ALL", errorsOnly: false });
  const set = (patch: Partial<Filters>) => setFilters((f) => ({ ...f, ...patch }));

  const source = frozen ?? frames;
  const filtered = source.filter((f) => matches(f, filters));
  const rows = filtered.slice(-MAX_ROWS).reverse();
  const ecus = stats ? Array.from(new Set(stats.per_id.map((r) => r.sender))).sort() : [];
  const messages = stats ? stats.per_id.flatMap((r) => (r.name ? [r.name] : [])) : [];

  if (!stats) {
    return (
      <div className="p-6 text-sm text-slate-500">
        {connection === "closed" ? "CAN stream unavailable." : "Connecting to the CAN stream…"}
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <StatsTiles stats={stats} />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_300px]">
        <PerIdTable rows={stats.per_id} />
        <PerEcu stats={stats} />
      </div>

      <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="mr-auto text-xs font-medium uppercase tracking-[0.15em] text-slate-400">
            Live traffic
            <span className="ml-3 normal-case tracking-normal text-slate-500">
              showing {rows.length} of {filtered.length} buffered frames
            </span>
          </h2>
          <input
            value={filters.id}
            onChange={(e) => set({ id: e.target.value })}
            placeholder="CAN ID, e.g. 0x100"
            aria-label="Filter by CAN ID"
            className={`${SELECT} w-48 font-mono`}
          />
          <select value={filters.ecu} onChange={(e) => set({ ecu: e.target.value })} aria-label="Filter by ECU" className={SELECT}>
            <option value="ALL">All ECUs</option>
            {ecus.map((e) => (
              <option key={e}>{e}</option>
            ))}
          </select>
          <select
            value={filters.message}
            onChange={(e) => set({ message: e.target.value })}
            aria-label="Filter by message"
            className={SELECT}
          >
            <option value="ALL">All messages</option>
            {messages.map((m) => (
              <option key={m}>{m}</option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={filters.errorsOnly}
              onChange={(e) => set({ errorsOnly: e.target.checked })}
              className="accent-sky-400"
            />
            Errors only
          </label>
          <button
            type="button"
            onClick={() => setFrozen(frozen ? null : frames)}
            className={`rounded-md px-3 py-1 text-sm font-medium ${
              frozen
                ? "bg-sky-500 text-slate-950 hover:bg-sky-400"
                : "border border-slate-600 text-slate-200 hover:bg-slate-800"
            }`}
          >
            {frozen ? "Resume" : "Pause"}
          </button>
        </div>

        <div className="mt-3 max-h-[560px] overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-slate-900">
              <tr className="text-left text-xs text-slate-500">
                <th className="py-1.5 pr-4 font-medium">Time</th>
                <th className="pr-4 font-medium">CAN ID</th>
                <th className="pr-4 font-medium">Message</th>
                <th className="pr-4 font-medium">ECU</th>
                <th className="pr-4 font-medium">DLC</th>
                <th className="pr-4 font-medium">Data</th>
                <th className="pr-4 font-medium">Decoded signals</th>
                <th className="font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((f) => (
                <tr key={f.seq} className="border-t border-slate-800/80 align-top">
                  <td className="whitespace-nowrap py-1.5 pr-4 font-mono text-xs text-slate-400">
                    {formatSimTime(f.t)}
                  </td>
                  <td className="pr-4 font-mono text-slate-100">{hexId(f.id)}</td>
                  <td className="whitespace-nowrap pr-4 text-slate-300">{f.name ?? "unknown"}</td>
                  <td className="pr-4 text-slate-400">{f.sender}</td>
                  <td className="pr-4 text-slate-400">{f.dlc}</td>
                  <td className="whitespace-nowrap pr-4 font-mono text-xs text-slate-300">{f.data}</td>
                  <td className="pr-4">
                    <Signals signals={f.signals} />
                  </td>
                  <td className="whitespace-nowrap">
                    {f.error ? (
                      <span title={f.error_detail ?? undefined}>
                        <Badge ok={false} label={f.error} />
                      </span>
                    ) : (
                      <Badge ok label="OK" />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <p className="py-6 text-center text-sm text-slate-500">No frames match the filters.</p>}
        </div>
      </section>
    </div>
  );
}
