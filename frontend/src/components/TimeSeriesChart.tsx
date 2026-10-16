import { memo, useEffect, useRef, useState, type MouseEvent } from "react";
import { formatSimTime } from "../utils/format";

export interface Threshold {
  value: number;
  label: string;
}

export interface Point {
  t: number;
  value: number | null;
}

interface TimeSeriesChartProps {
  title: string;
  unit: string;
  data: Point[];
  /** Visible time range [start, end] in simulation seconds. */
  domain: [number, number];
  yDomain: [number | "auto", number | "auto"];
  yTicks?: number[];
  threshold?: Threshold;
  digits?: number;
  /** Shared hover time, so all charts show the crosshair at the same moment. */
  hoverT: number | null;
  onHover: (t: number | null) => void;
}

const HEIGHT = 160;
const PAD = { top: 10, right: 12, bottom: 22, left: 44 };
const NICE_STEPS = [1, 2, 2.5, 5, 10];
const X_STEPS = [5, 10, 15, 30, 60];

function niceCeil(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step = NICE_STEPS.find((s) => s * magnitude >= value) ?? 10;
  return step * magnitude;
}

function autoTicks(max: number): number[] {
  const step = niceCeil(max / 4);
  return Array.from({ length: Math.floor(max / step) + 1 }, (_, i) => i * step);
}

/** Index of the point whose time is closest to t (data sorted by t). */
function nearest(data: Point[], t: number): number {
  let lo = 0;
  let hi = data.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (data[mid].t < t) lo = mid + 1;
    else hi = mid;
  }
  return lo > 0 && t - data[lo - 1].t < data[lo].t - t ? lo - 1 : lo;
}

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

// One measure per chart (no dual axes): a 2px line over a hairline grid, with
// a crosshair + tooltip on hover that is shared across all charts on the page.
// Plain SVG: cheap enough to redraw live, even in development builds.
function TimeSeriesChart({
  title,
  unit,
  data,
  domain,
  yDomain,
  yTicks,
  threshold,
  digits = 0,
  hoverT,
  onHover,
}: TimeSeriesChartProps) {
  const [boxRef, width] = useWidth<HTMLDivElement>();
  const latest = data.length ? data[data.length - 1].value : null;
  const [start, end] = domain;

  const values = data.flatMap((p) => (p.value === null ? [] : [p.value]));
  const yMin = yDomain[0] === "auto" ? 0 : yDomain[0];
  const yMax =
    yDomain[1] === "auto"
      ? niceCeil(Math.max(1, ...values, threshold?.value ?? 0) * 1.1)
      : yDomain[1];
  const ticks = yTicks ?? autoTicks(yMax);

  const plotW = Math.max(0, width - PAD.left - PAD.right);
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const x = (t: number) => PAD.left + ((t - start) / Math.max(1e-9, end - start)) * plotW;
  const y = (v: number) => PAD.top + plotH - ((v - yMin) / Math.max(1e-9, yMax - yMin)) * plotH;

  let path = "";
  let penDown = false;
  for (const p of data) {
    if (p.value === null) {
      penDown = false; // gap where the signal was missing
      continue;
    }
    const py = y(Math.min(Math.max(p.value, yMin), yMax));
    path += `${penDown ? "L" : "M"}${x(p.t).toFixed(1)} ${py.toFixed(1)}`;
    penDown = true;
  }

  const xStep = X_STEPS.find((s) => (end - start) / s <= 6) ?? 60;
  const xTicks: number[] = [];
  for (let ago = 0; ago <= end - start + 1e-6; ago += xStep) xTicks.push(end - ago);

  const hovered =
    hoverT !== null && data.length && hoverT >= start ? data[nearest(data, hoverT)] : null;

  const handleMove = (e: MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left;
    if (px < PAD.left || px > PAD.left + plotW || !data.length) return onHover(null);
    onHover(start + ((px - PAD.left) / plotW) * (end - start));
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
      <div ref={boxRef} className="relative mt-2" style={{ height: HEIGHT }}>
        {width > 0 && (
          <svg
            width={width}
            height={HEIGHT}
            role="img"
            aria-label={`${title} over the last ${Math.round(end - start)} seconds`}
            onMouseMove={handleMove}
            onMouseLeave={() => onHover(null)}
          >
            {ticks.map((v) => (
              <g key={v}>
                <line x1={PAD.left} x2={PAD.left + plotW} y1={y(v)} y2={y(v)} stroke="#1e293b" />
                <text
                  x={PAD.left - 8}
                  y={y(v)}
                  textAnchor="end"
                  dominantBaseline="central"
                  className="fill-slate-500 text-[11px]"
                >
                  {v}
                </text>
              </g>
            ))}
            {xTicks.map((t) => (
              <text
                key={t}
                x={x(t)}
                y={HEIGHT - 6}
                textAnchor="middle"
                className="fill-slate-500 text-[11px]"
              >
                {`${Math.round(t - end)}s`}
              </text>
            ))}
            {threshold && threshold.value <= yMax && (
              <g>
                <line
                  x1={PAD.left}
                  x2={PAD.left + plotW}
                  y1={y(threshold.value)}
                  y2={y(threshold.value)}
                  stroke="var(--color-status-critical)"
                  strokeOpacity={0.6}
                  strokeDasharray="4 4"
                />
                <text
                  x={PAD.left + plotW - 4}
                  y={y(threshold.value) - 5}
                  textAnchor="end"
                  className="fill-slate-400 text-[11px]"
                >
                  {threshold.label}
                </text>
              </g>
            )}
            <path
              d={path}
              fill="none"
              stroke="var(--color-accent)"
              strokeWidth={2}
              strokeLinejoin="round"
            />
            {hovered && (
              <g pointerEvents="none">
                <line
                  x1={x(hovered.t)}
                  x2={x(hovered.t)}
                  y1={PAD.top}
                  y2={PAD.top + plotH}
                  stroke="#475569"
                />
                {hovered.value !== null && (
                  <circle
                    cx={x(hovered.t)}
                    cy={y(Math.min(Math.max(hovered.value, yMin), yMax))}
                    r={4}
                    fill="var(--color-accent)"
                    stroke="#020617"
                    strokeWidth={2}
                  />
                )}
              </g>
            )}
          </svg>
        )}
        {hovered && (
          <div
            className="pointer-events-none absolute top-1 rounded-md border border-slate-700 bg-slate-950/95 px-3 py-2 text-xs shadow-lg"
            style={
              x(hovered.t) > width / 2
                ? { right: width - x(hovered.t) + 10 }
                : { left: x(hovered.t) + 10 }
            }
          >
            <div className="text-slate-400">{formatSimTime(hovered.t, 1)}</div>
            <div className="mt-0.5 font-semibold text-slate-100">
              {hovered.value === null ? "no data" : `${hovered.value.toFixed(digits)} ${unit}`}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

export default memo(TimeSeriesChart);
