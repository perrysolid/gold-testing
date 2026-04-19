// FR-9.1: Result screen — decision pill, weight/purity bands, evidence, "Why we said this"
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
};

// Pre-baked demo data — no backend call needed for judging demo
const DEMO: Record<string, AssessmentResult> = {
  "demo-genuine-22k-chain": {
    assessment_id: "demo-genuine-22k-chain",
    status: "done",
    decision: "PRE_APPROVE",
    headline: "Estimated 8–12 g, 22K, low risk",
    max_loan_inr: 52_800,
    ltv_applied: 0.85,
    weight_g: { low: 8, high: 12, confidence: 0.78 },
    purity: { karat_low: 22, karat_high: 22, confidence: 0.91 },
    authenticity_risk: { level: "LOW", score: 0.12 },
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
    assessment_id: "demo-plated-bangle",
    status: "done",
    decision: "NEEDS_VERIFICATION",
    headline: "Estimated 15–22 g, purity unclear, medium risk",
    weight_g: { low: 15, high: 22, confidence: 0.55 },
    purity: { karat_low: 18, karat_high: 22, confidence: 0.50 },
    authenticity_risk: { level: "MEDIUM", score: 0.48 },
    why: [
      "No BIS hallmark detected; purity cannot be confirmed from image alone.",
      "Brassy tint near edges suggests possible plating or wear.",
      "Weight estimate of 15–22 g has lower confidence without scale reference.",
      "Branch verification strongly recommended before loan approval.",
    ],
    next_steps_md: "Bring your jewellery to the nearest branch for expert verification.",
  },
  "demo-genuine-18k-ring": {
    assessment_id: "demo-genuine-18k-ring",
    status: "done",
    decision: "PRE_APPROVE",
    headline: "Estimated 3.5–5 g, 18K, low risk",
    max_loan_inr: 18_112,
    ltv_applied: 0.85,
    weight_g: { low: 3.5, high: 5, confidence: 0.74 },
    purity: { karat_low: 18, karat_high: 18, confidence: 0.82 },
    authenticity_risk: { level: "LOW", score: 0.15 },
    why: [
      "BIS logo detected with 750 purity mark (18K).",
      "Ring weight estimated at 3.5–5 g based on segmentation and scale.",
      "Even gold colour consistent with genuine 18K.",
      "Maximum loan ₹18,112 at 85% LTV on conservative weight.",
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

  useEffect(() => {
    if (!id) return;

    // Demo shortcut — no network call
    const demo = DEMO[id];
    if (demo) {
      const t = setTimeout(() => setResult(demo), 1200);
      return () => clearTimeout(t);
    }

    // Animated stage labels while polling
    const labelTimer = setInterval(() => {
      setStageIdx((i) => (i + 1) % STAGE_LABELS.length);
    }, 1800);

    // Poll every 2s until done or error
    let stopped = false;
    const poll = async () => {
      while (!stopped) {
        try {
          const r = await api.get<AssessmentResult>(`/assess/${id}`);
          if (r.status === "done" || r.status === "error") {
            setResult(r);
            stopped = true;
            clearInterval(labelTimer);
            return;
          }
        } catch { /* network hiccup — keep polling */ }
        await new Promise((res) => setTimeout(res, 2000));
      }
    };
    poll();
    return () => { stopped = true; clearInterval(labelTimer); };
  }, [id]);

  // Loading / processing state
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

  return (
    <div className="min-h-screen bg-ivory pb-10">
      <div className="max-w-lg mx-auto p-6 flex flex-col gap-5">

        {/* Decision pill */}
        <div className="flex flex-col items-center gap-2 pt-4">
          <span className={`px-6 py-2 rounded-full text-sm font-bold uppercase tracking-wide ${pillClass}`}>
            {decision.replace("_", " ")}
          </span>
          {result.headline && (
            <h1 className="text-xl font-headline text-brown text-center">{result.headline}</h1>
          )}
          {result.max_loan_inr != null && (
            <>
              <p className="text-3xl font-bold text-green-700">₹{result.max_loan_inr.toLocaleString("en-IN")}</p>
              {result.ltv_applied && (
                <p className="text-xs text-brown/40">at {Math.round(result.ltv_applied * 100)}% LTV · RBI 2025</p>
              )}
            </>
          )}
        </div>

        {/* Weight + Purity bands */}
        {(result.weight_g || result.purity) && (
          <div className="rounded-xl bg-white shadow-sm p-4 flex flex-col gap-4">
            {result.weight_g && (
              <div>
                <p className="text-xs text-brown/50 mb-1">Estimated Weight</p>
                <p className="font-semibold text-brown text-lg">{result.weight_g.low}–{result.weight_g.high} g</p>
                <ConfidenceBar value={result.weight_g.confidence}
                  label={`${Math.round(result.weight_g.confidence * 100)}% confidence`} />
              </div>
            )}
            {result.purity && (
              <div>
                <p className="text-xs text-brown/50 mb-1">Estimated Purity</p>
                <p className="font-semibold text-brown text-lg">
                  {result.purity.karat_low === result.purity.karat_high
                    ? `${result.purity.karat_low}K`
                    : `${result.purity.karat_low}K–${result.purity.karat_high}K`}
                </p>
                <ConfidenceBar value={result.purity.confidence}
                  label={`${Math.round(result.purity.confidence * 100)}% confidence`} />
              </div>
            )}
            {result.authenticity_risk && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-brown/50">Authenticity Risk:</span>
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                  result.authenticity_risk.level === "LOW" ? "bg-green-100 text-green-700"
                  : result.authenticity_risk.level === "HIGH" ? "bg-red-100 text-red-700"
                  : "bg-amber-100 text-amber-700"
                }`}>{result.authenticity_risk.level}</span>
              </div>
            )}
          </div>
        )}

        {/* Why we said this */}
        {result.why && result.why.length > 0 && (
          <div className="rounded-xl bg-white shadow-sm p-4">
            <h2 className="font-headline text-brown text-lg mb-3">Why we said this</h2>
            <ul className="flex flex-col gap-2">
              {result.why.filter(Boolean).map((b, i) => (
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
            <a href={`${BASE}/assess/${id}/pdf`} target="_blank" rel="noreferrer"
              className="min-touch w-full bg-brown text-ivory rounded-xl py-3 font-semibold text-center hover:bg-brown-dark transition-colors block">
              Download Pre-Approval Letter (PDF)
            </a>
          )}
          <button onClick={() => navigate("/")}
            className="min-touch w-full border border-brown/20 rounded-xl py-3 text-brown/60 hover:border-brown/40 transition-colors">
            Start New Assessment
          </button>
          <button onClick={() => navigate("/lender")}
            className="min-touch text-brown/30 text-sm text-center underline">
            View NBFC Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
