// FR-4 + FR-7: Self-declared data → POST /assess/start → upload artifacts → POST /assess/submit
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useCaptureStore } from "../lib/store";
import { api } from "../lib/api";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// Demo result IDs keyed by item type — used when backend is unavailable
const DEMO_RESULT: Record<string, string> = {
  ring:    "demo-genuine-18k-ring",
  chain:   "demo-genuine-22k-chain",
  bangle:  "demo-plated-bangle",
  earring: "demo-genuine-18k-ring",
  pendant: "demo-genuine-18k-ring",
  coin:    "demo-genuine-22k-chain",
};

async function uploadArtifact(assessmentId: string, kind: string, data: Uint8Array): Promise<string> {
  const blob = new Blob([data], { type: kind === "audio" ? "audio/wav" : "image/jpeg" });
  const sha256 = await crypto.subtle.digest("SHA-256", data).then((h) =>
    Array.from(new Uint8Array(h)).map((b) => b.toString(16).padStart(2, "0")).join("")
  );
  const form = new FormData();
  form.append("file", blob, `${kind}.${kind === "audio" ? "wav" : "jpg"}`);
  await fetch(`${BASE}/assess/upload/${assessmentId}/${kind}`, { method: "POST", body: form });
  return sha256;
}

export default function Review() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { captures, audio, itemType, setAssessmentId } = useCaptureStore();
  const [weight, setWeight] = useState("");
  const [karat, setKarat] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState("");
  const [error, setError] = useState("");
  const [backendDown, setBackendDown] = useState(false);

  const capturedCount = Object.keys(captures).length;

  const handleSubmit = async () => {
    setLoading(true);
    setError("");
    setBackendDown(false);
    try {
      // 1. Start assessment
      setStage(t("review.submitting"));
      let startRes: { assessment_id: string; upload_urls: Record<string, string> };
      try {
        startRes = await api.post<typeof startRes>("/assess/start", {});
      } catch (e) {
        // Backend unreachable — offer demo fallback
        setBackendDown(true);
        setLoading(false);
        setStage("");
        return;
      }

      const id = startRes.assessment_id;
      setAssessmentId(id);

      // 2. Upload captured images
      const artifacts: Array<{ kind: string; object_key: string; sha256: string }> = [];
      for (const [kind, data] of Object.entries(captures)) {
        if (!data) continue;
        setStage(`Uploading ${kind.replace("image_", "").replace("_", " ")}…`);
        const sha256 = await uploadArtifact(id, kind, data);
        artifacts.push({ kind, object_key: `${id}/${kind}`, sha256 });
      }

      // 3. Upload audio if present
      if (audio) {
        setStage("Uploading audio…");
        const sha256 = await uploadArtifact(id, "audio", audio);
        artifacts.push({ kind: "audio", object_key: `${id}/audio`, sha256, optional: true } as never);
      }

      // 4. Submit for ML pipeline
      setStage(t("review.submitting"));
      await api.post("/assess/submit", {
        assessment_id: id,
        item_declared: {
          type: itemType,
          declared_weight_g: weight ? parseFloat(weight) : null,
          declared_karat_stamp: karat || null,
          notes: notes || null,
        },
        artifacts,
        consent: { version: "v1", signed_at: new Date().toISOString() },
      });

      navigate(`/result/${id}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(`${t("common.error")} — ${msg}`);
    } finally {
      setLoading(false);
      setStage("");
    }
  };

  const handleDemoResult = () => {
    const demoId = DEMO_RESULT[itemType] ?? "demo-genuine-22k-chain";
    navigate(`/result/${demoId}`);
  };

  return (
    <div className="min-h-screen bg-ivory flex flex-col p-6 max-w-lg mx-auto gap-6">
      <h1 className="text-2xl font-headline text-brown mt-2">{t("review.title")}</h1>

      {/* Capture summary */}
      <div className="rounded-xl bg-white shadow-sm p-4">
        <p className="text-xs text-brown/50 mb-3 uppercase tracking-wide">{t("review.images")}</p>
        <div className="flex gap-3">
          {(["image_top", "image_side", "image_hallmark"] as const).map((k) => (
            <div key={k} className={`flex-1 h-16 rounded-lg flex items-center justify-center text-xs font-medium ${
              captures[k] ? "bg-green-100 text-green-700" : "bg-brown/5 text-brown/30"
            }`}>
              {captures[k] ? "✓" : "—"}
              <span className="ml-1">{k.replace("image_", "").replace("_", " ")}</span>
            </div>
          ))}
        </div>
        <div className="mt-3 flex items-center gap-2 text-xs text-brown/50">
          <span className="uppercase tracking-wide">{t("review.audio")}:</span>
          <span className={audio ? "text-green-600" : "text-brown/30"}>
            {audio ? t("review.audio_yes") : t("review.audio_no")}
          </span>
        </div>
        {capturedCount === 0 && (
          <p className="text-xs text-amber-600 mt-2">No images captured — use Load Sample in the camera step, or try the demo below.</p>
        )}
      </div>

      {/* Self-declaration (FR-4) */}
      <div className="rounded-xl bg-white shadow-sm p-4 flex flex-col gap-4">
        <p className="text-xs text-brown/50 uppercase tracking-wide">{t("review.item_type")}: <span className="font-semibold text-brown capitalize">{itemType}</span></p>
        <label className="flex flex-col gap-1">
          <span className="text-sm text-brown/60">{t("result.weight")} (g)</span>
          <input type="number" placeholder="e.g. 10.5" value={weight}
            onChange={(e) => setWeight(e.target.value)}
            className="border border-brown/20 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-gold" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm text-brown/60">{t("result.purity")}</span>
          <input type="text" placeholder="e.g. 916, 22K, BIS" value={karat}
            onChange={(e) => setKarat(e.target.value)}
            className="border border-brown/20 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-gold" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm text-brown/60">Notes (optional)</span>
          <textarea placeholder="e.g. gifted from mother, 10 years old" value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="border border-brown/20 rounded-lg p-3 resize-none h-20 focus:outline-none focus:ring-2 focus:ring-gold" />
        </label>
      </div>

      {/* Disclaimer */}
      <p className="text-xs text-brown/30 text-center">{t("review.disclaimer")}</p>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
          <p className="text-red-600 text-sm font-medium">Submission failed</p>
          <p className="text-red-500 text-xs mt-0.5">{error}</p>
        </div>
      )}

      {/* Backend unavailable — demo fallback */}
      {backendDown && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex flex-col gap-3">
          <p className="text-amber-800 text-sm font-semibold">Backend server not reachable</p>
          <p className="text-amber-700 text-xs leading-relaxed">
            Could not connect to <code className="bg-amber-100 px-1 rounded">localhost:8000</code>.
            For the hackathon demo, view a pre-computed result instead:
          </p>
          <div className="flex flex-col gap-2">
            <button
              onClick={() => navigate("/result/demo-genuine-22k-chain")}
              className="w-full bg-green-700 text-white rounded-lg py-2.5 text-sm font-semibold"
            >
              ✓ Demo: 22K Chain — Pre-Approved ₹52,800
            </button>
            <button
              onClick={() => navigate("/result/demo-genuine-18k-ring")}
              className="w-full bg-green-600 text-white rounded-lg py-2.5 text-sm font-semibold"
            >
              ✓ Demo: 18K Ring — Pre-Approved ₹18,112
            </button>
            <button
              onClick={() => navigate("/result/demo-plated-bangle")}
              className="w-full bg-amber-500 text-white rounded-lg py-2.5 text-sm font-semibold"
            >
              ⚠ Demo: Plated Bangle — Needs Verification
            </button>
          </div>
        </div>
      )}

      {/* Stage feedback */}
      {loading && stage && (
        <div className="flex items-center gap-3 text-brown/60 text-sm justify-center">
          <div className="w-4 h-4 rounded-full border-2 border-gold border-t-transparent animate-spin" />
          {stage}
        </div>
      )}

      <button onClick={handleSubmit} disabled={loading}
        className="min-touch w-full bg-brown text-ivory font-semibold rounded-xl py-4 text-lg shadow-md disabled:opacity-50 hover:bg-brown-dark transition-colors">
        {loading ? t("review.submitting") : t("review.submit")}
      </button>

      <button onClick={() => navigate("/capture")} className="text-brown/40 text-sm text-center underline">
        ← {t("capture.retake")}
      </button>
    </div>
  );
}
