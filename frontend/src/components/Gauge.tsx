// Automotive-style radial gauge: 270° sweep, value arc over a dim same-hue
// track, a pointer, tick scale and an optional redline zone. The number in the
// centre is the primary readout; the arc gives the at-a-glance position.

interface GaugeProps {
  label: string;
  unit: string;
  value: number | null;
  max: number;
  majorStep: number;
  minorStep: number;
  redlineFrom?: number;
  /** Scale labels are divided by this (e.g. 1000 for "x1000 rpm"). */
  labelDivisor?: number;
  format?: (value: number) => string;
  size?: number;
}

const SWEEP = 270;
const START = -SWEEP / 2;
const VIEW = 300;
const C = VIEW / 2;
const R = 124;

function polar(angleDeg: number, radius: number): [number, number] {
  const a = (angleDeg * Math.PI) / 180;
  return [C + radius * Math.sin(a), C - radius * Math.cos(a)];
}

function arcPath(fromDeg: number, toDeg: number, radius: number): string {
  const [x0, y0] = polar(fromDeg, radius);
  const [x1, y1] = polar(toDeg, radius);
  const large = toDeg - fromDeg > 180 ? 1 : 0;
  return `M ${x0} ${y0} A ${radius} ${radius} 0 ${large} 1 ${x1} ${y1}`;
}

export default function Gauge({
  label,
  unit,
  value,
  max,
  majorStep,
  minorStep,
  redlineFrom,
  labelDivisor = 1,
  format = (v) => Math.round(v).toString(),
  size = 300,
}: GaugeProps) {
  const fraction = value === null ? 0 : Math.min(Math.max(value / max, 0), 1);
  const angle = START + fraction * SWEEP;
  const angleOf = (v: number) => START + (v / max) * SWEEP;
  const inRedline = value !== null && redlineFrom !== undefined && value >= redlineFrom;
  const fill = inRedline ? "var(--color-status-critical)" : "var(--color-accent)";

  const ticks: { v: number; major: boolean }[] = [];
  for (let v = 0; v <= max + 1e-9; v += minorStep) {
    ticks.push({ v, major: Math.abs(v / majorStep - Math.round(v / majorStep)) < 1e-6 });
  }

  return (
    <div
      className="relative mx-auto"
      style={{ width: size, height: size }}
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value ?? undefined}
    >
      <svg viewBox={`0 0 ${VIEW} ${VIEW}`} className="absolute inset-0 h-full w-full">
        <path
          d={arcPath(START, START + SWEEP, R)}
          stroke="var(--color-accent-track)"
          strokeWidth={10}
          strokeLinecap="round"
          fill="none"
        />
        {redlineFrom !== undefined && (
          <path
            d={arcPath(angleOf(redlineFrom), START + SWEEP, R + 13)}
            stroke="var(--color-status-critical)"
            strokeWidth={4}
            fill="none"
          />
        )}
        <path
          d={arcPath(START, START + SWEEP, R)}
          pathLength={100}
          stroke={fill}
          strokeWidth={10}
          strokeLinecap="round"
          fill="none"
          strokeDasharray={`${fraction * 100} 100`}
          style={{ transition: "stroke-dasharray 120ms linear" }}
          opacity={value === null ? 0 : 1}
        />
        {ticks.map(({ v, major }) => {
          const a = angleOf(v);
          const [x0, y0] = polar(a, R - (major ? 22 : 15));
          const [x1, y1] = polar(a, R - 10);
          const [lx, ly] = polar(a, R - 38);
          const red = redlineFrom !== undefined && v >= redlineFrom;
          return (
            <g key={v}>
              <line
                x1={x0}
                y1={y0}
                x2={x1}
                y2={y1}
                stroke={red ? "var(--color-status-critical)" : major ? "#94a3b8" : "#475569"}
                strokeWidth={major ? 2 : 1}
              />
              {major && (
                <text
                  x={lx}
                  y={ly}
                  textAnchor="middle"
                  dominantBaseline="central"
                  className="fill-slate-400 text-[13px]"
                >
                  {v / labelDivisor}
                </text>
              )}
            </g>
          );
        })}
        <line
          x1={C}
          y1={C - R + 26}
          x2={C}
          y2={C - R - 8}
          stroke="#f1f5f9"
          strokeWidth={3}
          strokeLinecap="round"
          transform={`rotate(${angle} ${C} ${C})`}
          style={{ transition: "transform 120ms linear" }}
          opacity={value === null ? 0 : 1}
        />
      </svg>

      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
          {label}
        </span>
        <span className="mt-1 text-6xl font-semibold text-slate-50">
          {value === null ? "--" : format(value)}
        </span>
        <span className="mt-1 text-sm text-slate-400">{unit}</span>
      </div>
    </div>
  );
}
