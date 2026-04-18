// FR-9.1: Evidence tile shown in result screen
type Props = {
  kind: string;
  payload: Record<string, unknown>;
  confidence: number;
};

export default function EvidenceTile({ kind, payload, confidence }: Props) {
  return (
    <div className="rounded-lg bg-brown/5 p-3 text-xs">
      <div className="flex justify-between mb-1">
        <span className="font-medium text-brown/70 uppercase tracking-wide">{kind.replace(/_/g, " ")}</span>
        <span className="text-brown/40">{Math.round(confidence * 100)}%</span>
      </div>
      <pre className="text-brown/50 overflow-auto max-h-20 text-[10px]">{JSON.stringify(payload, null, 2)}</pre>
    </div>
  );
}
