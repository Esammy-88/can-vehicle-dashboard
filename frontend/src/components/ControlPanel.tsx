import { useState, type ReactNode } from "react";
import { setSimulationSpeed, simulationAction, updateControls } from "../services/api";
import type {
  Cluster,
  Controls,
  ControlsUpdate,
  DoorName,
  Headlights,
  Selector,
  SimulationStatus,
  SpeedFactor,
  TurnIndicator,
} from "../types/api";

function send(update: ControlsUpdate) {
  updateControls(update).catch((error) => console.error(error));
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <h2 className="text-xs font-medium uppercase tracking-[0.15em] text-slate-400">{title}</h2>
      <div className="mt-3 space-y-4">{children}</div>
    </section>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm text-slate-400">{label}</span>
      {children}
    </div>
  );
}

interface SegmentedProps<T extends string | number> {
  options: readonly T[];
  value: T | undefined;
  onChange: (value: T) => void;
  render?: (value: T) => ReactNode;
  disabled?: boolean;
}

function Segmented<T extends string | number>({
  options,
  value,
  onChange,
  render = (v) => String(v),
  disabled,
}: SegmentedProps<T>) {
  return (
    <div className="flex rounded-md border border-slate-700 bg-slate-950 p-0.5">
      {options.map((option) => (
        <button
          key={option}
          type="button"
          disabled={disabled}
          aria-pressed={option === value}
          onClick={() => onChange(option)}
          className={`min-w-10 rounded px-2.5 py-1 text-sm font-medium transition-colors disabled:opacity-40 ${
            option === value
              ? "bg-slate-700 text-slate-50"
              : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
          }`}
        >
          {render(option)}
        </button>
      ))}
    </div>
  );
}

function Toggle({ on, onChange, label }: { on: boolean; onChange: (on: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={() => onChange(!on)}
      className={`relative h-6 w-11 rounded-full transition-colors ${on ? "bg-sky-500" : "bg-slate-700"}`}
    >
      <span
        className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all ${on ? "left-[22px]" : "left-0.5"}`}
      />
    </button>
  );
}

interface PedalProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
}

// Shows the local value while dragging so streamed updates don't fight the thumb.
function Pedal({ label, value, onChange }: PedalProps) {
  const [draft, setDraft] = useState<number | null>(null);
  const shown = draft ?? value;
  const commit = (v: number) => {
    setDraft(v);
    onChange(v);
  };
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-slate-400">{label}</span>
        <span className="text-sm font-medium text-slate-200">{Math.round(shown)} %</span>
      </div>
      <div className="mt-1.5 flex items-center gap-2">
        <button
          type="button"
          onClick={() => onChange(Math.max(0, value - 10))}
          className="rounded border border-slate-700 px-2 text-sm text-slate-300 hover:bg-slate-800"
          aria-label={`Decrease ${label}`}
        >
          −
        </button>
        <input
          type="range"
          min={0}
          max={100}
          step={5}
          value={shown}
          aria-label={label}
          onChange={(e) => commit(Number(e.target.value))}
          onPointerUp={() => setDraft(null)}
          onKeyUp={() => setDraft(null)}
          className="flex-1 accent-sky-400"
        />
        <button
          type="button"
          onClick={() => onChange(Math.min(100, value + 10))}
          className="rounded border border-slate-700 px-2 text-sm text-slate-300 hover:bg-slate-800"
          aria-label={`Increase ${label}`}
        >
          +
        </button>
      </div>
    </div>
  );
}

function selectorHint(controls: Controls, cluster: Cluster): string | null {
  const actual = cluster.selector;
  if (actual === null || controls.gear_selector === actual) return null;
  if (actual === "P") return `Press the brake to shift into ${controls.gear_selector}`;
  if (controls.gear_selector === "P" || controls.gear_selector === "R") {
    return `Stop the vehicle to select ${controls.gear_selector}`;
  }
  return null;
}

const DOOR_LABELS: [DoorName, string][] = [
  ["front_left", "FL"],
  ["front_right", "FR"],
  ["rear_left", "RL"],
  ["rear_right", "RR"],
];

const INDICATOR_LABELS: Record<TurnIndicator, string> = {
  OFF: "Off",
  LEFT: "◀",
  RIGHT: "▶",
  HAZARD: "Hazard",
};

interface ControlPanelProps {
  controls: Controls | null;
  cluster: Cluster | null;
  simulation: SimulationStatus | null;
}

export default function ControlPanel({ controls, cluster, simulation }: ControlPanelProps) {
  if (!controls || !cluster || !simulation) {
    return (
      <Section title="Controls">
        <p className="text-sm text-slate-500">Waiting for the backend…</p>
      </Section>
    );
  }
  const hint = selectorHint(controls, cluster);

  return (
    <div className="space-y-6">
      <Section title="Driver">
        <Row label="Ignition">
          <button
            type="button"
            onClick={() => send({ ignition: !controls.ignition })}
            aria-pressed={controls.ignition}
            className={`rounded-md px-4 py-1.5 text-sm font-semibold transition-colors ${
              controls.ignition
                ? "bg-sky-500 text-slate-950 hover:bg-sky-400"
                : "border border-slate-600 text-slate-200 hover:bg-slate-800"
            }`}
          >
            {controls.ignition ? "ON" : "OFF"}
          </button>
        </Row>
        <Pedal label="Throttle" value={controls.throttle} onChange={(v) => send({ throttle: v })} />
        <Pedal label="Brake" value={controls.brake} onChange={(v) => send({ brake: v })} />
        <div>
          <Row label="Gear selector">
            <Segmented<Selector>
              options={["P", "R", "N", "D"]}
              value={cluster.selector ?? undefined}
              onChange={(v) => send({ gear_selector: v })}
            />
          </Row>
          {hint && <p className="mt-1.5 text-right text-xs text-slate-400">{hint}</p>}
        </div>
        <Row label="Headlights">
          <Segmented<Headlights>
            options={["OFF", "LOW", "HIGH"]}
            value={controls.headlights}
            onChange={(v) => send({ headlights: v })}
          />
        </Row>
        <Row label="Indicators">
          <Segmented<TurnIndicator>
            options={["OFF", "LEFT", "RIGHT", "HAZARD"]}
            value={controls.turn_indicator}
            onChange={(v) => send({ turn_indicator: v })}
            render={(v) => INDICATOR_LABELS[v]}
          />
        </Row>
        <Row label="Doors open">
          <div className="flex gap-1">
            {DOOR_LABELS.map(([door, label]) => (
              <button
                key={door}
                type="button"
                aria-pressed={controls.doors_open[door]}
                onClick={() => send({ doors_open: { [door]: !controls.doors_open[door] } })}
                className={`w-10 rounded-md border py-1 text-sm font-medium ${
                  controls.doors_open[door]
                    ? "border-slate-500 bg-slate-700 text-slate-50"
                    : "border-slate-700 text-slate-400 hover:bg-slate-800"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </Row>
        <Row label="Seatbelt fastened">
          <Toggle
            label="Seatbelt fastened"
            on={controls.seatbelt_fastened}
            onChange={(on) => send({ seatbelt_fastened: on })}
          />
        </Row>
      </Section>

      <Section title="Simulation">
        <Row label={`Time ${formatTime(simulation.time_s)}`}>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => simulationAction(simulation.running ? "pause" : "start")}
              className="rounded-md border border-slate-600 px-3 py-1 text-sm text-slate-200 hover:bg-slate-800"
            >
              {simulation.running ? "Pause" : "Start"}
            </button>
            <button
              type="button"
              onClick={() => simulationAction("reset")}
              className="rounded-md border border-slate-600 px-3 py-1 text-sm text-slate-200 hover:bg-slate-800"
            >
              Reset
            </button>
          </div>
        </Row>
        <Row label="Speed">
          <Segmented<SpeedFactor>
            options={[0.5, 1, 2, 5]}
            value={simulation.speed}
            onChange={(v) => setSimulationSpeed(v)}
            render={(v) => `${v}×`}
          />
        </Row>
      </Section>
    </div>
  );
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
