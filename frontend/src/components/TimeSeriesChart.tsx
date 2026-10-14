import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from "recharts";
import { formatSimTime } from "../utils/format";

export interface Threshold {
  value: number;
  label: string;
}

interface TimeSeriesChartProps {
  title: string;
  unit: string;
  data: { t: number; value: number | null }[];
  /** Visible time range [start, end] in simulation seconds. */
  domain: [number, number];
  yDomain: [number | "auto", number | "auto"];
  yTicks?: number[];
  threshold?: Threshold;
  digits?: number;
}

const AXIS_TICK = { fill: "#64748b", fontSize: 11 };

// One measure per chart (no dual axes): a 2px line over a hairline grid, a
// crosshair + tooltip on hover, synced across all charts on the page.
export default function TimeSeriesChart({
  title,
  unit,
  data,
  domain,
  yDomain,
  yTicks,
  threshold,
  digits = 0,
}: TimeSeriesChartProps) {
  const latest = data.length ? data[data.length - 1].value : null;
  const end = domain[1];

  const renderTooltip = ({ active, payload }: TooltipContentProps) => {
    if (!active || !payload?.length) return null;
    const raw = payload[0].value;
    const value = typeof raw === "number" ? raw : null;
    const point = payload[0].payload as { t: number };
    return (
      <div className="rounded-md border border-slate-700 bg-slate-950/95 px-3 py-2 text-xs shadow-lg">
        <div className="text-slate-400">{formatSimTime(point.t, 1)}</div>
        <div className="mt-0.5 font-semibold text-slate-100">
          {value === null ? "no data" : `${value.toFixed(digits)} ${unit}`}
        </div>
      </div>
    );
  };

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex items-baseline justify-between">
        <h2 className="text-xs font-medium uppercase tracking-[0.15em] text-slate-400">{title}</h2>
        <span className="text-lg font-semibold text-slate-50">
          {latest === null ? "--" : latest.toFixed(digits)}
          <span className="ml-1 text-xs font-normal text-slate-400">{unit}</span>
        </span>
      </div>
      <div className="mt-2 h-40" role="img" aria-label={`${title} over time`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} syncId="telemetry" margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid vertical={false} stroke="#1e293b" />
            <XAxis
              dataKey="t"
              type="number"
              domain={domain}
              allowDataOverflow
              tick={AXIS_TICK}
              tickFormatter={(t: number) => `${Math.round(t - end)}s`}
              axisLine={false}
              tickLine={false}
              minTickGap={24}
            />
            <YAxis
              domain={yDomain}
              ticks={yTicks}
              tick={AXIS_TICK}
              axisLine={false}
              tickLine={false}
              width={48}
              allowDecimals={false}
            />
            {threshold && (
              <ReferenceLine
                y={threshold.value}
                stroke="var(--color-status-critical)"
                strokeOpacity={0.6}
                strokeDasharray="4 4"
                label={{
                  value: threshold.label,
                  position: "insideTopRight",
                  fill: "#94a3b8",
                  fontSize: 11,
                }}
              />
            )}
            <Tooltip
              content={renderTooltip}
              cursor={{ stroke: "#475569", strokeWidth: 1 }}
              isAnimationActive={false}
            />
            <Line
              type="linear"
              dataKey="value"
              stroke="var(--color-accent)"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, stroke: "#020617", strokeWidth: 2 }}
              isAnimationActive={false}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
