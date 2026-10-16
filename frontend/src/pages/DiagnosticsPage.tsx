import FaultPanel from "../components/FaultPanel";
import StatTile from "../components/StatTile";
import { clearDtcHistory } from "../services/api";
import type { DtcRecord, LogEvent, Snapshot } from "../types/api";
import { formatSimTime } from "../utils/format";

function OnlineBadge({ online }: { online: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm font-semibold">
      <span
        className={`h-2.5 w-2.5 rounded-full ${online ? "bg-status-good" : "bg-status-critical"}`}
        aria-hidden="true"
      />
      <span className="text-slate-100">{online ? "ONLINE" : "OFFLINE"}</span>
    </span>
  );
}

function Panel({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-medium uppercase tracking-[0.15em] text-slate-400">{title}</h2>
        {action}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function DtcTable({ rows, history }: { rows: DtcRecord[]; history?: boolean }) {
  if (rows.length === 0) {
    return <p className="text-sm text-slate-500">{history ? "No codes recorded" : "No active trouble codes"}</p>;
  }
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-xs text-slate-500">
          <th className="py-1.5 pr-4 font-medium">Code</th>
          <th className="pr-4 font-medium">ECU</th>
          <th className="pr-4 font-medium">Description</th>
          <th className="pr-4 font-medium">Set</th>
          {history && <th className="font-medium">Cleared</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={`${r.code}-${r.ecu}-${r.set_at}`} className="border-t border-slate-800/80 text-slate-300">
            <td className="py-1.5 pr-4 font-mono font-semibold text-slate-100">{r.code}</td>
            <td className="pr-4">{r.ecu}</td>
            <td className="pr-4">{r.description}</td>
            <td className="whitespace-nowrap pr-4 font-mono text-xs">{formatSimTime(r.set_at, 1)}</td>
            {history && (
              <td className="whitespace-nowrap font-mono text-xs">
                {r.cleared_at === null ? (
                  <span className="font-sans text-slate-100">active</span>
                ) : (
                  formatSimTime(r.cleared_at, 1)
                )}
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const FAULT_EVENTS = new Set(["FAULT_INJECTED", "FAULT_CLEARED", "ECU_TIMEOUT", "ECU_ONLINE", "ECU_CRASH"]);

export default function DiagnosticsPage({ snapshot, events }: { snapshot: Snapshot | null; events: LogEvent[] }) {
  if (!snapshot) {
    return <div className="p-6 text-sm text-slate-500">Waiting for the backend…</div>;
  }
  const d = snapshot.diagnostics;
  const busOnline = !snapshot.bus_down && d.last_frame_ago_s !== null && d.last_frame_ago_s < 1.0;
  const faultHistory = events.filter((e) => FAULT_EVENTS.has(e.event)).slice(-40).reverse();

  return (
    <div className="grid gap-6 p-6 xl:grid-cols-[minmax(0,1fr)_380px]">
      <div className="space-y-6">
        <div className="grid gap-6 2xl:grid-cols-2">
          <Panel title="ECU status">
            <table className="w-full table-fixed text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500">
                  <th className="py-1.5 pr-3 font-medium">ECU</th>
                  <th className="w-32 pr-3 font-medium">Status</th>
                  <th className="w-28 whitespace-nowrap pr-3 text-right font-medium">Last frame</th>
                  <th className="w-20 pr-3 text-right font-medium">Timeouts</th>
                  <th
                    className="w-32 whitespace-nowrap text-right font-medium"
                    title="Repeated or skipped alive counters"
                  >
                    Counter errors
                  </th>
                </tr>
              </thead>
              <tbody className="tabular-nums">
                {d.ecus.map((e) => (
                  <tr key={e.node} className="border-t border-slate-800/80">
                    <td className="truncate whitespace-nowrap py-2 pr-3">
                      <div className="truncate text-slate-100">{e.name}</div>
                      <div className="truncate text-xs text-slate-500">
                        {e.last_message ?? "nothing received"}
                      </div>
                    </td>
                    <td className="whitespace-nowrap pr-3">
                      <OnlineBadge online={e.online} />
                    </td>
                    <td className="whitespace-nowrap pr-3 text-right text-slate-300">
                      {e.last_seen_ago_s === null ? "never" : `${Math.round(e.last_seen_ago_s * 1000)} ms ago`}
                    </td>
                    <td className="pr-3 text-right text-slate-300">{e.timeouts}</td>
                    <td className="text-right text-slate-300">{e.counter_errors}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          <Panel title="CAN bus">
            <div className="mb-4">
              <OnlineBadge online={busOnline} />
              {snapshot.bus_down && <span className="ml-3 text-sm text-slate-400">bus interruption injected</span>}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <StatTile label="Message rate" value={snapshot.bus.messages_per_s.toFixed(0)} unit="/s" />
              <StatTile label="Errors" value={snapshot.bus.errors.toString()} />
              <StatTile
                label="Last communication"
                value={d.last_frame_ago_s === null ? "--" : Math.round(d.last_frame_ago_s * 1000).toString()}
                unit="ms ago"
              />
              <StatTile label="Total frames" value={snapshot.bus.total_frames.toLocaleString()} />
            </div>
          </Panel>
        </div>

        <Panel title="Active trouble codes">
          <DtcTable rows={d.active_dtcs} />
        </Panel>

        <div className="grid gap-6 lg:grid-cols-2">
          <Panel
            title="Trouble code history"
            action={
              <button
                type="button"
                onClick={() => clearDtcHistory().catch(console.error)}
                className="rounded-md border border-slate-600 px-2.5 py-0.5 text-xs text-slate-200 hover:bg-slate-800"
              >
                Clear history
              </button>
            }
          >
            <div className="max-h-80 overflow-auto">
              <DtcTable rows={d.dtc_history} history />
            </div>
          </Panel>

          <Panel title="Fault history">
            {faultHistory.length === 0 ? (
              <p className="text-sm text-slate-500">No faults or ECU timeouts yet</p>
            ) : (
              <ul className="max-h-80 space-y-1.5 overflow-auto text-sm">
                {faultHistory.map((e) => (
                  <li key={e.seq} className="flex gap-3">
                    <span className="shrink-0 font-mono text-xs leading-5 text-slate-500">
                      {formatSimTime(e.sim_time, 1)}
                    </span>
                    <span className="text-slate-300">{e.message}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>

      <aside>
        <FaultPanel active={snapshot.faults} />
      </aside>
    </div>
  );
}
