/** Simulation time as mm:ss.mmm (hours are added if the run gets that long). */
export function formatSimTime(t: number, decimals = 3): string {
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = (t % 60).toFixed(decimals).padStart(decimals ? 3 + decimals : 2, "0");
  const mm = m.toString().padStart(2, "0");
  return h ? `${h}:${mm}:${s}` : `${mm}:${s}`;
}

export function hexId(id: number): string {
  return `0x${id.toString(16).toUpperCase().padStart(3, "0")}`;
}

export function formatValue(v: number | string, digits = 2): string {
  if (typeof v === "string") return v;
  return Number.isInteger(v) ? v.toString() : v.toFixed(digits);
}
