interface StatusIndicatorProps {
  label: string;
  online: boolean;
}

export default function StatusIndicator({ label, online }: StatusIndicatorProps) {
  return (
    <div className="flex items-center gap-2 font-mono text-xs uppercase tracking-wider">
      <span
        className={`h-2.5 w-2.5 rounded-full ${
          online ? "bg-emerald-400 shadow-[0_0_8px] shadow-emerald-400" : "bg-red-500"
        }`}
      />
      <span className="text-slate-400">{label}</span>
      <span className={online ? "text-emerald-400" : "text-red-400"}>
        {online ? "ONLINE" : "OFFLINE"}
      </span>
    </div>
  );
}
