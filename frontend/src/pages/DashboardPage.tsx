import ControlPanel from "../components/ControlPanel";
import EngineStateBadge from "../components/EngineStateBadge";
import FaultPanel from "../components/FaultPanel";
import Gauge from "../components/Gauge";
import GearDisplay from "../components/GearDisplay";
import { FuelIcon, GearboxIcon, TemperatureIcon } from "../components/Icons";
import LinearMeter, { type Tone } from "../components/LinearMeter";
import Telltales from "../components/Telltales";
import WarningPanel from "../components/WarningPanel";
import type { Snapshot } from "../types/api";

// Thresholds mirror the cluster ECU's warning rules (backend/app/ecus/dashboard.py).
const coolantTone = (v: number): Tone => (v >= 110 ? "critical" : v >= 105 ? "warning" : "normal");
const oilTone = (v: number): Tone => (v >= 130 ? "critical" : v >= 120 ? "warning" : "normal");
const transTone = (v: number): Tone => (v >= 120 ? "critical" : v >= 105 ? "warning" : "normal");
const fuelTone = (v: number): Tone => (v < 5 ? "critical" : v < 15 ? "warning" : "normal");

function Stat({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-[0.15em] text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-semibold text-slate-100">
        {value}
        {unit && <span className="ml-1 text-sm font-normal text-slate-400">{unit}</span>}
      </div>
    </div>
  );
}

export default function DashboardPage({ snapshot }: { snapshot: Snapshot | null }) {
  const c = snapshot?.cluster ?? null;
  const fmt = (v: number | null | undefined, digits = 0) =>
    v === null || v === undefined ? "--" : v.toFixed(digits);

  return (
    <div>
      <div className="grid gap-6 p-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <main className="space-y-6">
          <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
            <div className="grid items-center gap-6 lg:grid-cols-[1fr_auto_1fr]">
              <Gauge
                label="Speed"
                unit="km/h"
                value={c?.speed_kmh ?? null}
                max={240}
                majorStep={20}
                minorStep={10}
              />
              <div className="flex flex-col items-center gap-6">
                <GearDisplay cluster={c} />
                <EngineStateBadge state={c?.engine_state ?? null} />
              </div>
              <Gauge
                label="Engine speed"
                unit="rpm"
                value={c?.rpm ?? null}
                max={8000}
                majorStep={1000}
                minorStep={500}
                redlineFrom={6500}
                labelDivisor={1000}
                format={(v) => (Math.round(v / 10) * 10).toString()}
              />
            </div>
            <div className="mt-4 border-t border-slate-800 pt-4">
              <Telltales cluster={c} />
            </div>
          </section>

          <section className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-4">
            <LinearMeter
              label="Coolant"
              icon={<TemperatureIcon />}
              value={c?.coolant_c ?? null}
              unit="°C"
              min={40}
              max={130}
              tone={coolantTone}
              marks={[105, 110]}
            />
            <LinearMeter
              label="Oil"
              icon={<TemperatureIcon />}
              value={c?.oil_c ?? null}
              unit="°C"
              min={40}
              max={150}
              tone={oilTone}
              marks={[120, 130]}
            />
            <LinearMeter
              label="Transmission"
              icon={<GearboxIcon />}
              value={c?.trans_c ?? null}
              unit="°C"
              min={40}
              max={140}
              tone={transTone}
              marks={[105, 120]}
            />
            <LinearMeter
              label="Fuel"
              icon={<FuelIcon />}
              value={c?.fuel_pct ?? null}
              unit="%"
              min={0}
              max={100}
              tone={fuelTone}
              marks={[15]}
              format={(v) => v.toFixed(0)}
            />
          </section>

          <section className="grid grid-cols-2 gap-6 rounded-lg border border-slate-800 bg-slate-900/60 p-4 sm:grid-cols-4">
            <Stat label="Throttle" value={fmt(c?.throttle)} unit="%" />
            <Stat label="Engine load" value={fmt(c?.engine_load)} unit="%" />
            <Stat label="Odometer" value={fmt(c?.odometer_km, 2)} unit="km" />
            <Stat label="Sim time" value={snapshot ? `${snapshot.simulation.time_s.toFixed(0)}` : "--"} unit="s" />
          </section>
        </main>

        <aside className="space-y-6">
          <WarningPanel warnings={c?.warnings ?? null} />
          <ControlPanel
            controls={snapshot?.controls ?? null}
            cluster={c}
            simulation={snapshot?.simulation ?? null}
          />
          <FaultPanel active={snapshot?.faults ?? null} />
        </aside>
      </div>
    </div>
  );
}
