import ReadoutTile from "../components/ReadoutTile";
import StatusIndicator from "../components/StatusIndicator";
import { useBackendHealth } from "../hooks/useBackendHealth";

const PLACEHOLDER_READOUTS = [
  { label: "Speed", unit: "km/h" },
  { label: "RPM", unit: "rpm" },
  { label: "Gear" },
  { label: "Coolant", unit: "°C" },
  { label: "Oil", unit: "°C" },
  { label: "Fuel", unit: "%" },
];

export default function DashboardPage() {
  const { online, health } = useBackendHealth();

  return (
    <div className="min-h-full">
      <header className="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div>
          <h1 className="font-mono text-lg font-semibold tracking-wide text-slate-100">
            CAN VEHICLE DASHBOARD
          </h1>
          <p className="font-mono text-xs text-slate-500">
            Software-in-the-loop CAN network simulation
          </p>
        </div>
        <div className="flex items-center gap-6">
          {health && (
            <span className="font-mono text-xs text-slate-500">
              CAN MODE: <span className="text-sky-400">{health.can_mode.toUpperCase()}</span>
            </span>
          )}
          <StatusIndicator label="Backend" online={online} />
        </div>
      </header>

      <main className="p-6">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
          {PLACEHOLDER_READOUTS.map(({ label, unit }) => (
            <ReadoutTile key={label} label={label} value="--" unit={unit} />
          ))}
        </div>
      </main>
    </div>
  );
}
