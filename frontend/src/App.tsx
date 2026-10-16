import DemoBanner from "./components/DemoBanner";
import StatusIndicator from "./components/StatusIndicator";
import { useHashRoute, type Route } from "./hooks/useHashRoute";
import { useTelemetry } from "./hooks/useTelemetry";
import CanMonitorPage from "./pages/CanMonitorPage";
import DashboardPage from "./pages/DashboardPage";
import DiagnosticsPage from "./pages/DiagnosticsPage";
import GraphsPage from "./pages/GraphsPage";
import LogsPage from "./pages/LogsPage";

const TABS: { route: Route; label: string }[] = [
  { route: "dashboard", label: "Dashboard" },
  { route: "monitor", label: "CAN Monitor" },
  { route: "graphs", label: "Graphs" },
  { route: "diagnostics", label: "Diagnostics" },
  { route: "logs", label: "Logs" },
];

export default function App() {
  // Telemetry lives at the top so graph history keeps filling on every page.
  const telemetry = useTelemetry();
  const { connection, snapshot } = telemetry;
  const route = useHashRoute();

  return (
    <div className="min-h-full">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 px-6 py-3">
        <div className="flex items-center gap-8">
          <div>
            <h1 className="text-lg font-semibold tracking-wide text-slate-100">CAN Vehicle Dashboard</h1>
            <p className="text-xs text-slate-500">Software-in-the-loop CAN network simulation</p>
          </div>
          <nav className="flex gap-1" aria-label="Pages">
            {TABS.map((tab) => (
              <a
                key={tab.route}
                href={`#/${tab.route}`}
                aria-current={route === tab.route ? "page" : undefined}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  route === tab.route
                    ? "bg-slate-800 text-slate-50"
                    : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
                }`}
              >
                {tab.label}
              </a>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-6 text-xs text-slate-500">
          {snapshot && snapshot.faults.length > 0 && (
            <a
              href="#/diagnostics"
              className="flex items-center gap-2 rounded-full border border-status-critical/60 px-2.5 py-1 text-slate-200 hover:bg-slate-900"
            >
              <span className="h-2 w-2 rounded-full bg-status-critical" aria-hidden="true" />
              {snapshot.faults.length} fault{snapshot.faults.length > 1 ? "s" : ""} injected
            </a>
          )}
          {snapshot && (
            <span>
              CAN <span className="text-slate-300">{snapshot.can_mode.toUpperCase()}</span>
              {snapshot.can_mode === "auto" && (
                <>
                  {" → "}
                  <span className="text-slate-300">{snapshot.can_backend.toUpperCase()}</span>
                </>
              )}
            </span>
          )}
          {snapshot && (
            <span>
              Simulation{" "}
              <span className="text-slate-300">
                {snapshot.simulation.running ? "running" : "paused"} · {snapshot.simulation.speed}×
              </span>
            </span>
          )}
          <StatusIndicator state={connection} />
        </div>
      </header>

      {connection === "closed" && (
        <div className="border-b border-status-warning/40 bg-slate-900 px-6 py-2 text-sm text-slate-300">
          Backend unreachable — reconnecting. Start it with{" "}
          <code className="font-mono text-slate-100">
            uvicorn app.main:app --app-dir backend --reload --reload-dir backend
          </code>
        </div>
      )}

      <DemoBanner demo={snapshot?.demo} />

      {route === "dashboard" && <DashboardPage snapshot={snapshot} />}
      {route === "monitor" && <CanMonitorPage />}
      {route === "diagnostics" && <DiagnosticsPage snapshot={snapshot} events={telemetry.events} />}
      {route === "logs" && <LogsPage events={telemetry.events} />}
      {route === "graphs" && <GraphsPage history={telemetry.history} />}
    </div>
  );
}
