// FR-9.1: Result screen — decision pill, weight/purity bands, evidence, "Why we said this"
import { useParams, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import ConfidenceBar from "../components/ConfidenceBar";
import EvidenceTile from "../components/EvidenceTile";
import { api } from "../lib/api";

type AssessmentResult = {
  assessment_id: string;
  decision: string;
  headline: string;
  max_loan_inr?: number;
  ltv_applied?: number;
  weight_g?: { low: number; high: number; confidence: number };
  purity?: { karat_low: number; karat_high: number; confidence: number };
  authenticity_risk?: { level: string; score: number };
  why: string[];
  next_steps_md?: string;
};

const DECISION_COLORS: Record<string, string> = {
  PRE_APPROVE: "bg-green-700 text-white",
  NEEDS_VERIFICATION: "bg-amber-500 text-white",
  REJECT: "bg-red-700 text-white",
};

// Demo data for scaffold / judging demo
const DEMO: Record<string, AssessmentResult> = {
  "demo-genuine-22k-chain": {
    assessment_id: "demo-genuine-22k-chain",
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
      "Colour analysis consistent with 22K gold.",
      "Audio tap test confirms solid karat metal.",
      "Final valuation requires physical branch verification.",
    ],
    next_steps_md: "Visit a branch within 14 days to complete physical verification and disbursal.",
  },
  "demo-plated-bangle": {
    assessment_id: "demo-plated-bangle",
    decision: "NEEDS_VERIFICATION",
    headline: "Estimated 15–22 g, purity unclear, medium risk",
    max_loan_inr: undefined,
    weight_g: { low: 15, high: 22, confidence: 0.55 },
    purity: { karat_low: 18, karat_high: 22, confidence: 0.50 },
    authenticity_risk: { level: "MEDIUM", score: 0.48 },
    why: [
      "No BIS hallmark detected; purity cannot be confirmed from image alone.",
      "Brassy tint detected near edges, suggesting possible plating.",
      "Weight estimate of 15–22 g has lower confidence without scale reference.",
      "Branch verification strongly recommended before loan approval.",
    ],
    next_steps_md: "Bring your jewellery to the nearest branch for expert verification.",
  },
};

export default function Result() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    const demo = DEMO[id];
    if (demo) {
      setTimeout(() => { setResult(demo); setLoading(false); }, 800);
      return;
    }
    api.get<AssessmentResult>(`/assess/${id}`)
      .then((r) => { setResult(r); setLoading(false); })
      .catch(() => setLoading(false));
  }, [id]);

  if (loading) return (
    <div className="min-h-screen bg-ivory flex flex-col items-center justify-center gap-4 p-6">
      <div className="w-12 h-12 rounded-full border-4 border-gold border-t-transparent animate-spin" />
      <p className="text-brown/60 text-sm" aria-live="polite">Analysing your jewellery…</p>
    </div>
  );

  if (!result) return (
    <div className="min-h-screen bg-ivory flex items-center justify-center">
      <p className="text-brown/60">Assessment not found.</p>
    </div>
  );

  const pillClass = DECISION_COLORS[result.decision] || "bg-gray-500 text-white";

  return (
    <div className="min-h-screen bg-ivory pb-10">
      <div className="max-w-lg mx-auto p-6 flex flex-col gap-6">
        {/* Decision pill */}
        <div className="flex flex-col items-center gap-2 pt-4">
          <span className={`px-6 py-2 rounded-full text-sm font-bold uppercase tracking-wide ${pillClass}`}>
            {result.decision.replace("_", " ")}
          </span>
          <h1 className="text-xl font-headline text-brown text-center">{result.headline}</h1>
          {result.max_loan_inr && (
            <p className="text-3xl font-bold text-green-700">₹{result.max_loan_inr.toLocaleString("en-IN")}</p>
          )}
          {result.ltv_applied && (
            <p className="text-xs text-brown/40">at {Math.round(result.ltv_applied * 100)}% LTV (RBI 2025)</p>
          )}
        </div>

        {/* Bands */}
        {result.weight_g && (
          <div className="rounded-xl bg-white shadow-sm p-4 flex flex-col gap-3">
            <div>
              <p className="text-xs text-brown/50 mb-1">Estimated Weight</p>
              <p className="font-semibold text-brown">{result.weight_g.low}–{result.weight_g.high} g</p>
              <ConfidenceBar value={result.weight_g.confidence} label={`${Math.round(result.weight_g.confidence * 100)}% confidence`} />
            </div>
            {result.purity && (
              <div>
                <p className="text-xs text-brown/50 mb-1">Estimated Purity</p>
                <p className="font-semibold text-brown">{result.purity.karat_low}K–{result.purity.karat_high}K</p>
                <ConfidenceBar value={result.purity.confidence} label={`${Math.round(result.purity.confidence * 100)}% confidence`} />
              </div>
            )}
            {result.authenticity_risk && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-brown/50">Risk:</span>
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
        {result.why.length > 0 && (
          <div className="rounded-xl bg-white shadow-sm p-4">
            <h2 className="font-headline text-brown text-lg mb-3">Why we said this</h2>
            <ul className="flex flex-col gap-2">
              {result.why.map((bullet, i) => (
                <li key={i} className="flex gap-2 text-sm text-brown/80">
                  <span className="text-gold mt-0.5">•</span>
                  <span>{bullet}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Next steps */}
        {result.next_steps_md && (
          <div className="rounded-xl bg-brown/5 p-4 text-sm text-brown/70">
            {result.next_steps_md}
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-col gap-3">
          <button className="min-touch w-full bg-brown text-ivory rounded-xl py-3 font-semibold hover:bg-brown-dark transition-colors">
            Download Pre-Approval Letter (PDF)
          </button>
          <button onClick={() => navigate("/")} className="min-touch w-full border border-brown/20 rounded-xl py-3 text-brown/60 hover:border-brown/40 transition-colors">
            Start New Assessment
          </button>
        </div>
      </div>
    </div>
  );
}
