// FR-2.4: Real-time quality feedback chip
type Props = { label: string; ok: boolean };

export default function QualityChip({ label, ok }: Props) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
      ok ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"
    }`}>
      {ok ? "✓" : "✗"} {label}
    </span>
  );
}
