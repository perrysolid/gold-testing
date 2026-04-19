// FR-9.1: Result screen — decision pill, weight/purity bands, flags, evidence, "Why we said this"
// Polls GET /assess/{id} until status=done, then renders full result.
import { useParams, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import ConfidenceBar from "../components/ConfidenceBar";
import { api } from "../lib/api";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type WeightBand = { low: number; high: number; confidence: number };
type PurityBand = { karat_low: number; karat_high: number; confidence: number };
type RiskInfo   = { level: string; score: number };

type AssessmentResult = {
  assessment_id: string;
  status: string;
  decision?: string;
  headline?: string;
  max_loan_inr?: number;
  ltv_applied?: number;
  weight_g?: WeightBand;
  purity?: PurityBand;
  authenticity_risk?: RiskInfo;
  why?: string[];
  next_steps_md?: string;
  flags?: string[];
  evidence?: { kind: string; confidence: number; payload: Record<string, unknown> }[];
};

// Pre-baked demo — no backend call needed for judging demos
const DEMO: Record<string, AssessmentResult> = {
  "demo-genuine-22k-chain": {
    assessment_id: "demo-genuine-22k-chain", status: "done", decision: "PRE_APPROVE",
    headline: "Estimated 8–12 g, 22K, low risk",
    max_loan_inr: 52_800, ltv_applied: 0.85,
    weight_g: { low: 8, high: 12, confidence: 0.78 },
    purity: { karat_low: 22, karat_high: 22, confidence: 0.91 },
    authenticity_risk: { level: "LOW", score: 0.12 },
    flags: ["HALLMARK_VALID_BIS", "COIN_SCALE_DETECTED"],
    why: [
      "Valid BIS hallmark with readable 916 purity mark detected.",
      "ArUco scale marker confirms weight estimate of 8–12 g (78% confidence).",
      "Colour analysis consistent with 22K gold — warm yellow, low variance.",
      "Audio tap test confirms solid karat metal, not hollow or plated.",
      "Final valuation requires physical branch verification.",
    ],
    next_steps_md: "Visit a branch within 14 days to complete physical verification and disbursal.",
  },
  "demo-plated-bangle": {
    assessment_id: "demo-plated-bangle", status: "done", decision: "NEEDS_VERIFICATION",
    headline: "Estimated 15–22 g, purity unclear, medium risk",
    weight_g: { low: 15, high: 22, confidence: 0.55 },
    purity: { karat_low: 18, karat_high: 22, confidence: 0.50 },
    authenticity_risk: { level: "MEDIUM", score: 0.48 },
    flags: ["HALLMARK_MISSING_CAPPED"],
    why: [
      "No BIS hallmark detected; purity cannot be confirmed from image alone.",
      "Brassy tint near edges suggests possible plating or wear.",
      "Weight estimate of 15–22 g has lower confidence without scale reference.",
      "Branch verification strongly recommended before loan approval.",
    ],
    next_steps_md: "Bring your jewellery to the nearest branch for expert verification.",
  },
  "demo-genuine-18k-ring": {
    assessment_id: "demo-genuine-18k-ring", status: "done", decision: "PRE_APPROVE",
    headline: "Estimated 3.5–5 g, 18K, low risk",
    max_loan_inr: 18_112, ltv_applied: 0.85,
    weight_g: { low: 3.5, high: 5, confidence: 0.74 },
    purity: { karat_low: 18, karat_high: 18, confidence: 0.82 },
    authenticity_risk: { level: "LOW", score: 0.15 },
    flags: ["HALLMARK_BIS_LOGO"],
    why: [
      "BIS logo detected with 750 purity mark (18K).",
      "Ring weight estimated at 3.5–5.0 g based on segmentation and scale.",
      "Even gold colour and surface uniformity indicate genuine 18K composition.",
      "Maximum loan ₹18,112 calculated at 85% LTV on conservative weight.",
      "Please visit a branch within 14 days to complete disbursal.",
    ],
    next_steps_md: "Visit a branch within 14 days to complete physical verification and disbursal.",
  },
};

const PILL: Record<string, string> = {
  PRE_APPROVE: "bg-green-700 text-white",
  NEEDS_VERIFICATION: "bg-amber-500 text-white",
  REJECT: "bg-red-700 text-white",
};

const RISK_BG: Record<string, string> = {
  LOW: "bg-green-500", MEDIUM: "bg-amber-500", HIGH: "bg-red-500",
};

const FLAG_STYLE: Record<string, string> = {
  HALLMARK_VALID_BIS:      "bg-green-50  text-green-700 border-green-200",
  HALLMARK_BIS_LOGO:       "bg-green-50  text-green-700 border-green-200",
  COIN_SCALE_DETECTED:     "bg-blue-50   text-blue-700  border-blue-200",
  HALLMARK_MISSING_CAPPED: "bg-amber-50  text-amber-700 border-amber-200",
  WEIGHT_INCONSISTENCY:    "bg-red-50    text-red-700   border-red-200",
  FAKE_HALLMARK_DETECTED:  "bg-red-50    text-red-700   border-red-200",
  HIGH_RISK:               "bg-red-50    text-red-700   border-red-200",
  DUPLICATE_SUBMISSION:    "bg-red-50    text-red-700   border-red-200",
};

const STAGE_LABELS = [
  "Analysing image…",
  "Reading hallmark…",
  "Estimating weight…",
  "Checking authenticity…",
  "Computing loan eligibility…",
];

export default function Result() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [stageIdx, setStageIdx] = useState(0);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!id) return;
    const demo = DEMO[id];
    if (demo) {
      const t = setTimeout(() => setResult(demo), 1200);
      return () => clearTimeout(t);
    }
    const labelTimer = setInterval(() => setStageIdx((i) => (i + 1) % STAGE_LABELS.length), 1800);
    let stopped = false;
    const poll = async () => {
      while (!stopped) {
        try {
          const r = await api.get<AssessmentResult>(`/assess/${id}`);
          if (r.status === "done" || r.status === "error") {
            setResult(r); stopped = true; clearInterval(labelTimer); return;
          }
        } catch { /* keep polling */ }
        await new Promise((res) => setTimeout(res, 2000));
      }
    };
    poll();
    return () => { stopped = true; clearInterval(labelTimer); };
  }, [id]);

  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  if (!result) {
    return (
      <div className="min-h-screen bg-ivory flex flex-col items-center justify-center gap-6 p-6">
        <div className="w-16 h-16 rounded-full border-4 border-gold border-t-transparent animate-spin" />
        <p className="text-brown/70 font-medium" aria-live="polite">{STAGE_LABELS[stageIdx]}</p>
        <div className="flex gap-1">
          {STAGE_LABELS.map((_, i) => (
            <div key={i} className={`w-1.5 h-1.5 rounded-full ${i === stageIdx ? "bg-gold" : "bg-brown/15"}`} />
          ))}
        </div>
      </div>
    );
  }

  if (result.status === "error") {
    return (
      <div className="min-h-screen bg-ivory flex flex-col items-center justify-center gap-4 p-6">
        <span className="text-4xl">⚠️</span>
        <p className="text-brown font-semibold">Assessment failed</p>
        <p className="text-brown/50 text-sm text-center">The pipeline encountered an error. Please try again or visit a branch.</p>
        <button onClick={() => navigate("/")} className="min-touch px-6 py-3 bg-brown text-ivory rounded-xl">Go Home</button>
      </div>
    );
  }

  const decision = result.decision ?? "NEEDS_VERIFICATION";
  const pillClass = PILL[decision] ?? "bg-gray-500 text-white";
  const risk = result.authenticity_risk;

  return (
    <div className="min-h-screen bg-ivory pb-12">
      <div className="max-w-lg mx-auto p-6 flex flex-col gap-5">

        {/* Decision pill + headline */}
        <div className="flex flex-col items-center gap-2 pt-4">
          <span className={`px-6 py-2 rounded-full text-sm font-bold uppercase tracking-wide ${pillClass}`}>
            {decision.replace(/_/g, " ")}
          </span>
          {result.headline && (
            <h1 className="text-xl font-headline text-brown text-center mt-1">{result.headline}</h1>
          )}
          {result.max_loan_inr != null && (
            <>
              <p className="text-4xl font-bold text-green-700 mt-1">
                ₹{result.max_loan_inr.toLocaleString("en-IN")}
              </p>
              {result.ltv_applied && (
                <p className="text-xs text-brown/40">
                  at {Math.round(result.ltv_applied * 100)}% LTV · RBI Gold Loan Directions 2025
                </p>
              )}
            </>
          )}
        </div>

        {/* Weight + Purity + Risk */}
        {(result.weight_g || result.purity || risk) && (
          <div className="rounded-xl bg-white shadow-sm p-4 flex flex-col gap-4">
            {result.weight_g && (
              <div>
                <p className="text-xs text-brown/40 mb-1 uppercase tracking-wide">Estimated Weight</p>
                <p className="font-semibold text-brown text-lg">{result.weight_g.low}–{result.weight_g.high} g</p>
                <ConfidenceBar value={result.weight_g.confidence}
                  label={`${Math.round(result.weight_g.confidence * 100)}% confidence`} />
              </div>
            )}
            {result.purity && (
              <div>
                <p className="text-xs text-brown/40 mb-1 uppercase tracking-wide">Estimated Purity</p>
                <p className="font-semibold text-brown text-lg">
                  {result.purity.karat_low === result.purity.karat_high
                    ? `${result.purity.karat_low}K`
                    : `${result.purity.karat_low}K–${result.purity.karat_high}K`}
                </p>
                <ConfidenceBar value={result.purity.confidence}
                  label={`${Math.round(result.purity.confidence * 100)}% confidence`} />
              </div>
            )}
            {risk && (
              <div>
                <p className="text-xs text-brown/40 mb-1 uppercase tracking-wide">Authenticity Risk</p>
                <div className="flex items-center gap-3">
                  <div className="flex-1 bg-brown/10 rounded-full h-2 overflow-hidden">
                    <div
                      className={`h-2 rounded-full transition-all ${RISK_BG[risk.level] ?? "bg-gray-400"}`}
                      style={{ width: `${Math.round(risk.score * 100)}%` }}
                    />
                  </div>
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                    risk.level === "LOW"    ? "bg-green-100 text-green-700"
                    : risk.level === "HIGH" ? "bg-red-100 text-red-700"
                    :                         "bg-amber-100 text-amber-700"
                  }`}>{risk.level} ({Math.round(risk.score * 100)}%)</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Flags */}
        {(result.flags ?? []).length > 0 && (
          <div className="rounded-xl bg-white shadow-sm p-4">
            <p className="text-xs text-brown/40 mb-2 uppercase tracking-wide">Signal Flags</p>
            <div className="flex flex-wrap gap-2">
              {(result.flags ?? []).map((f) => (
                <span
                  key={f}
                  className={`text-xs px-2.5 py-1 rounded-full border font-medium ${
                    FLAG_STYLE[f] ?? "bg-brown/5 text-brown/50 border-brown/15"
                  }`}
                >
                  {f.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Why we said this */}
        {(result.why ?? []).length > 0 && (
          <div className="rounded-xl bg-white shadow-sm p-4">
            <h2 className="font-headline text-brown text-lg mb-3">Why we said this</h2>
            <ul className="flex flex-col gap-2">
              {(result.why ?? []).filter(Boolean).map((b, i) => (
                <li key={i} className="flex gap-2 text-sm text-brown/80">
                  <span className="text-gold mt-0.5 shrink-0">•</span>
                  <span>{b.replace(/^[-•]\s*/, "")}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Next steps */}
        {result.next_steps_md && (
          <div className="rounded-xl bg-brown/5 p-4 text-sm text-brown/70 leading-relaxed">
            {result.next_steps_md}
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-col gap-3">
          {result.status === "done" && decision !== "REJECT" && (
            <a
              href={`${BASE}/assess/${result.assessment_id}/pdf`}
              target="_blank" rel="noreferrer"
              className="min-touch w-full bg-brown text-ivory rounded-xl py-3.5 font-semibold text-center hover:bg-brown-dark transition-colors block"
            >
              Download Pre-Approval Letter (PDF)
            </a>
          )}
          <button
            onClick={handleShare}
            className="min-touch w-full border border-brown/20 rounded-xl py-3 text-brown/60 hover:border-brown/40 transition-colors text-sm"
          >
            {copied ? "Link copied!" : "Share this result"}
          </button>
          <button
            onClick={() => navigate("/")}
            className="min-touch w-full border border-brown/15 rounded-xl py-3 text-brown/40 hover:border-brown/30 transition-colors text-sm"
          >
            Start New Assessment
          </button>
          <button
            onClick={() => navigate("/lender")}
            className="text-brown/25 text-xs text-center underline"
          >
            NBFC Dashboard
          </button>
        </div>

        <p className="text-xs text-brown/25 text-center leading-relaxed">
          This is a preliminary estimate only. Final valuation requires physical
          inspection at your nearest branch. Valid 14 days from assessment date.
        </p>
      </div>
    </div>
  );
}
