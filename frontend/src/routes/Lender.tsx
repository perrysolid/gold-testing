// FR-10.1 / FR-10.2: NBFC dashboard — live assessment queue, analytics, CSV export
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type Row = {
  id: string;
  status: string;
  decision: string | null;
  item_type: string;
  created_at: string;
  max_loan_inr: number | null;
  purity_confidence: number | null;
  weight_confidence: number | null;
  risk_score: number | null;
  flags: string[];
};

const PILL: Record<string, string> = {
  PRE_APPROVE:        "bg-green-100 text-green-700",
  NEEDS_VERIFICATION: "bg-amber-100 text-amber-700",
  REJECT:             "bg-red-100 text-red-700",
};

const RISK_DOT: Record<string, string> = {
  LOW:    "bg-green-400",
  MEDIUM: "bg-amber-400",
  HIGH:   "bg-red-400",
};

function riskLevel(score: number | null): string {
  if (score == null) return "—";
  if (score < 0.30) return "LOW";
  if (score < 0.65) return "MEDIUM";
  return "HIGH";
}

type Filter = "ALL" | "PRE_APPROVE" | "NEEDS_VERIFICATION" | "REJECT";

export default function Lender() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>("ALL");

  useEffect(() => {
    api.get<Row[]>("/assess/")
      .then(setRows)
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, []);

  // Analytics computed from live data
  const today = new Date().toISOString().slice(0, 10);
  const todayRows = rows.filter((r) => r.created_at.startsWith(today));
  const approved  = rows.filter((r) => r.decision === "PRE_APPROVE");
  const needsVerify = rows.filter((r) => r.decision === "NEEDS_VERIFICATION");
  const rejected  = rows.filter((r) => r.decision === "REJECT");
  const totalLoan = approved.reduce((s, r) => s + (r.max_loan_inr ?? 0), 0);

  const visible = filter === "ALL" ? rows : rows.filter((r) => r.decision === filter);

  const handleCsvExport = () => {
    window.open(`${BASE}/assess/export.csv`, "_blank");
  };

  const tiles = [
    { label: t("lender.total"),        value: rows.length,         sub: t("lender.today", { n: todayRows.length }) },
    { label: t("lender.approved"),     value: approved.length,     sub: t("lender.pipeline", { amount: `${(totalLoan / 1_00_000).toFixed(1)}L` }) },
    { label: t("lender.needs_verify"), value: needsVerify.length,  sub: t("lender.pending_branch") },
    { label: t("lender.rejected"),     value: rejected.length,     sub: t("lender.not_eligible") },
  ];

  const filterLabels: Record<Filter, string> = {
    ALL: t("lender.filter_all"),
    PRE_APPROVE: t("lender.approved"),
    NEEDS_VERIFICATION: t("lender.needs_verify"),
    REJECT: t("lender.rejected"),
  };

  return (
    <div className="min-h-screen bg-ivory">
      <div className="max-w-5xl mx-auto p-6 flex flex-col gap-6">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-headline text-brown">{t("lender.title")}</h1>
            <p className="text-xs text-brown/40 mt-0.5">{t("lender.subtitle")}</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => navigate("/")}
              className="text-xs text-brown/40 border border-brown/15 rounded-lg px-3 py-1.5 hover:border-brown/30 transition-colors"
            >
              {t("lender.back")}
            </button>
            <button
              onClick={handleCsvExport}
              className="text-xs text-brown/60 border border-brown/20 rounded-lg px-3 py-1.5 hover:border-gold hover:text-gold transition-colors"
            >
              {t("lender.export")}
            </button>
          </div>
        </div>

        {/* Analytics tiles */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {tiles.map((tile) => (
            <div key={tile.label} className="rounded-xl bg-white shadow-sm p-4 text-center">
              <p className="text-2xl font-bold text-brown">{loading ? "—" : tile.value}</p>
              <p className="text-xs font-medium text-brown/60 mt-0.5">{tile.label}</p>
              <p className="text-xs text-brown/30 mt-0.5">{loading ? "" : tile.sub}</p>
            </div>
          ))}
        </div>

        {/* Filter tabs */}
        <div className="flex gap-2 flex-wrap">
          {(["ALL", "PRE_APPROVE", "NEEDS_VERIFICATION", "REJECT"] as Filter[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`text-xs px-3 py-1.5 rounded-full border transition-all ${
                filter === f
                  ? "bg-brown text-ivory border-brown"
                  : "border-brown/15 text-brown/50 hover:border-brown/30"
              }`}
            >
              {filterLabels[f]}
            </button>
          ))}
        </div>

        {/* Table */}
        <div className="rounded-xl bg-white shadow-sm overflow-x-auto">
          {loading ? (
            <div className="p-12 text-center text-brown/30 text-sm">{t("lender.loading")}</div>
          ) : visible.length === 0 ? (
            <div className="p-12 text-center text-brown/30 text-sm">{t("lender.empty")}</div>
          ) : (
            <table className="w-full text-sm min-w-[640px]">
              <thead className="bg-brown/5 text-brown/50 text-xs uppercase tracking-wide">
                <tr>
                  <th className="p-3 text-left">{t("lender.col_type")}</th>
                  <th className="p-3 text-left">{t("lender.col_decision")}</th>
                  <th className="p-3 text-left">{t("lender.col_risk")}</th>
                  <th className="p-3 text-left">{t("lender.col_purity")}</th>
                  <th className="p-3 text-left">{t("lender.col_loan")}</th>
                  <th className="p-3 text-left">{t("lender.col_flags")}</th>
                  <th className="p-3 text-left">{t("lender.col_created")}</th>
                  <th className="p-3" />
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => {
                  const rl = riskLevel(row.risk_score);
                  return (
                    <tr
                      key={row.id}
                      className="border-t border-brown/5 hover:bg-brown/[0.03] transition-colors cursor-pointer"
                      onClick={() => navigate(`/result/${row.id}`)}
                    >
                      <td className="p-3 capitalize font-medium text-brown">{row.item_type || "—"}</td>
                      <td className="p-3">
                        {row.decision ? (
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${PILL[row.decision] ?? "bg-gray-100 text-gray-600"}`}>
                            {row.decision.replace("_", " ")}
                          </span>
                        ) : (
                          <span className="text-brown/30">{row.status}</span>
                        )}
                      </td>
                      <td className="p-3">
                        <div className="flex items-center gap-1.5">
                          <span className={`w-2 h-2 rounded-full ${RISK_DOT[rl] ?? "bg-gray-300"}`} />
                          <span className="text-brown/60 text-xs">{rl}</span>
                        </div>
                      </td>
                      <td className="p-3 text-brown/60">
                        {row.purity_confidence != null
                          ? `${Math.round(row.purity_confidence * 100)}%`
                          : "—"}
                      </td>
                      <td className="p-3 font-medium text-brown">
                        {row.max_loan_inr != null
                          ? `₹${row.max_loan_inr.toLocaleString("en-IN")}`
                          : "—"}
                      </td>
                      <td className="p-3 max-w-[160px]">
                        <div className="flex flex-wrap gap-1">
                          {(row.flags ?? []).slice(0, 2).map((f) => (
                            <span key={f} className="text-xs bg-brown/8 text-brown/50 px-1.5 py-0.5 rounded">
                              {f.replace(/_/g, " ")}
                            </span>
                          ))}
                          {(row.flags ?? []).length > 2 && (
                            <span className="text-xs text-brown/30">+{row.flags.length - 2}</span>
                          )}
                        </div>
                      </td>
                      <td className="p-3 text-brown/30 text-xs whitespace-nowrap">
                        {new Date(row.created_at).toLocaleString("en-IN", {
                          day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
                        })}
                      </td>
                      <td className="p-3 text-brown/20 text-xs">→</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <p className="text-xs text-brown/20 text-center">
          {t("lender.disclaimer")}
        </p>
      </div>
    </div>
  );
}
