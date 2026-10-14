import { useState } from "react";
import TimeSeriesChart, { type Threshold } from "../components/TimeSeriesChart";
import type { HistorySample } from "../types/api";

const RANGES = [
  { seconds: 30, label: "30 s" },
  { seconds: 60, label: "1 min" },
  { seconds: 120, label: "2 min" },
  { seconds: 300, label: "5 min" },
];
const MAX_POINTS = 300; // per chart; keeps rendering cheap at the 5-minute range

type Metric = Exclude<keyof HistorySample, "seq" | "t">;

interface ChartSpec {
  metric: Metric;
  title: string;
  unit: string;
  yDomain: [number | "auto", number | "auto"];
  yTicks?: number[];
  threshold?: Threshold;
  digits?: number;
}

// Thresholds match the cluster ECU's warning rules.
const CHARTS: ChartSpec[] = [
  { metric: "speed_kmh", title: "Vehicle speed", unit: "km/h", yDomain: [0, "auto"] },
  {
    metric: "rpm",
    title: "Engine speed",
    unit: "rpm",
    yDomain: [0, 8000],
    yTicks: [0, 2000, 4000, 6000, 8000],
    threshold: { value: 6500, label: "Redline" },
  },
  {
    metric: "coolant_c",
    title: "Coolant temperature",
    unit: "°C",
    yDomain: [0, 130],
    yTicks: [0, 40, 80, 120],
    threshold: { value: 110, label: "Overheat" },
  },
  {
    metric: "oil_c",
    title: "Oil temperature",
    unit: "°C",
    yDomain: [0, 150],
    yTicks: [0, 50, 100, 150],
    threshold: { value: 130, label: "High oil temp" },
  },
  {
    metric: "fuel_pct",
    title: "Fuel level",
    unit: "%",
    yDomain: [0, 100],
    yTicks: [0, 25, 50, 75, 100],
    threshold: { value: 15, label: "Low fuel" },
    digits: 1,
  },
  {
    metric: "engine_load",
    title: "Engine load",
    unit: "%",
    yDomain: [0, 100],
    yTicks: [0, 25, 50, 75, 100],
  },
  { metric: "can_rate", title: "CAN message rate", unit: "frames/s", yDomain: [0, "auto"] },
];

export default function GraphsPage({ history }: { history: HistorySample[] }) {
  const [range, setRange] = useState(60);

  const end = history.length ? history[history.length - 1].t : 0;
  const start = end - range;
  const visible = history.filter((s) => s.t >= start);
  const stride = Math.max(1, Math.ceil(visible.length / MAX_POINTS));
  const points = visible.filter((_, i) => i % stride === 0 || i === visible.length - 1);

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="text-sm text-slate-400">
          Values decoded from CAN by the instrument cluster, sampled every 0.2 s of simulation time.
        </p>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-400">Time range</span>
          <div className="flex rounded-md border border-slate-700 bg-slate-950 p-0.5">
            {RANGES.map((r) => (
              <button
                key={r.seconds}
                type="button"
                aria-pressed={range === r.seconds}
                onClick={() => setRange(r.seconds)}
                className={`rounded px-3 py-1 text-sm font-medium transition-colors ${
                  range === r.seconds
                    ? "bg-slate-700 text-slate-50"
                    : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {history.length === 0 ? (
        <p className="text-sm text-slate-500">Waiting for data…</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {CHARTS.map((chart) => (
            <TimeSeriesChart
              key={chart.metric}
              title={chart.title}
              unit={chart.unit}
              yDomain={chart.yDomain}
              yTicks={chart.yTicks}
              threshold={chart.threshold}
              digits={chart.digits}
              domain={[start, end]}
              data={points.map((s) => ({ t: s.t, value: s[chart.metric] }))}
            />
          ))}
        </div>
      )}
    </div>
  );
}
