type Props = { value: number; label: string };

export default function ConfidenceBar({ value, label }: Props) {
  const pct = Math.round(value * 100);
  const color = pct >= 75 ? "bg-green-500" : pct >= 50 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2 mt-1">
      <div className="flex-1 h-1.5 bg-brown/10 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-brown/40 whitespace-nowrap">{label}</span>
    </div>
  );
}
