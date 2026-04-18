// FR-10.1: NBFC dashboard — assessment queue with risk flags
// TODO [FR-10.1, FR-10.2]: Wire to GET /assess/ and add CSV export
import { useNavigate } from "react-router-dom";

const DEMO_ROWS = [
  { id: "demo-genuine-22k-chain", type: "chain", decision: "PRE_APPROVE", risk: "LOW", conf: "91%", created: "2025-01-15 10:23" },
  { id: "demo-plated-bangle", type: "bangle", decision: "NEEDS_VERIFICATION", risk: "MEDIUM", conf: "50%", created: "2025-01-15 09:47" },
  { id: "demo-genuine-18k-ring", type: "ring", decision: "PRE_APPROVE", risk: "LOW", conf: "82%", created: "2025-01-14 16:05" },
];

const PILL: Record<string, string> = {
  PRE_APPROVE: "bg-green-100 text-green-700",
  NEEDS_VERIFICATION: "bg-amber-100 text-amber-700",
  REJECT: "bg-red-100 text-red-700",
};

export default function Lender() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-ivory p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-headline text-brown">NBFC Dashboard</h1>
        <button className="text-sm text-brown/50 border border-brown/20 rounded-lg px-3 py-1.5 hover:border-brown/40">
          Export CSV
        </button>
      </div>

      {/* Analytics tiles */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: "Today", value: "3" },
          { label: "Pre-Approved", value: "2" },
          { label: "Needs Verify", value: "1" },
        ].map((tile) => (
          <div key={tile.label} className="rounded-xl bg-white shadow-sm p-4 text-center">
            <p className="text-2xl font-bold text-brown">{tile.value}</p>
            <p className="text-xs text-brown/50">{tile.label}</p>
          </div>
        ))}
      </div>

      {/* Table */}
      <div className="rounded-xl bg-white shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-brown/5 text-brown/60">
            <tr>
              <th className="p-3 text-left">Type</th>
              <th className="p-3 text-left">Decision</th>
              <th className="p-3 text-left">Risk</th>
              <th className="p-3 text-left">Confidence</th>
              <th className="p-3 text-left">Created</th>
              <th className="p-3" />
            </tr>
          </thead>
          <tbody>
            {DEMO_ROWS.map((row) => (
              <tr key={row.id} className="border-t border-brown/5 hover:bg-brown/5 transition-colors cursor-pointer" onClick={() => navigate(`/result/${row.id}`)}>
                <td className="p-3 capitalize">{row.type}</td>
                <td className="p-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${PILL[row.decision]}`}>
                    {row.decision.replace("_", " ")}
                  </span>
                </td>
                <td className="p-3 text-brown/60">{row.risk}</td>
                <td className="p-3 text-brown/60">{row.conf}</td>
                <td className="p-3 text-brown/40 text-xs">{row.created}</td>
                <td className="p-3 text-brown/30 text-xs">→</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
