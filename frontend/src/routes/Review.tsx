// FR-4 + FR-7: Self-declared data → POST /assess/start → upload artifacts → POST /assess/submit
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCaptureStore } from "../lib/store";
import { api } from "../lib/api";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function uploadArtifact(assessmentId: string, kind: string, data: Uint8Array): Promise<string> {
  const blob = new Blob([data], { type: kind === "audio" ? "audio/webm" : "image/jpeg" });
  const sha256 = await crypto.subtle.digest("SHA-256", data).then((h) =>
    Array.from(new Uint8Array(h)).map((b) => b.toString(16).padStart(2, "0")).join("")
  );
  // POST to local upload endpoint
  const form = new FormData();
  form.append("file", blob, `${kind}.${kind === "audio" ? "webm" : "jpg"}`);
  await fetch(`${BASE}/assess/upload/${assessmentId}/${kind}`, { method: "POST", body: form });
  return sha256;
}

export default function Review() {
  const navigate = useNavigate();
  const { captures, audio, itemType, setAssessmentId } = useCaptureStore();
  const [weight, setWeight] = useState("");
  const [karat, setKarat] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState("");
  const [error, setError] = useState("");

  const capturedCount = Object.keys(captures).length;

  const handleSubmit = async () => {
    setLoading(true);
    setError("");
    try {
      // 1. Start assessment
      setStage("Starting assessment…");
      const startRes = await api.post<{ assessment_id: string; upload_urls: Record<string, string> }>(
        "/assess/start", {}
      );
      const id = startRes.assessment_id;
      setAssessmentId(id);

      // 2. Upload captured images
      const artifacts: Array<{ kind: string; object_key: string; sha256: string }> = [];
      for (const [kind, data] of Object.entries(captures)) {
        if (!data) continue;
        setStage(`Uploading ${kind.replace("_", " ")}…`);
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
      setStage("Submitting for analysis…");
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
    } catch (e) {
      setError("Submission failed. Check your connection and try again.");
      console.error(e);
    } finally {
      setLoading(false);
      setStage("");
    }
  };

  return (
    <div className="min-h-screen bg-ivory flex flex-col p-6 max-w-lg mx-auto gap-6">
      <h1 className="text-2xl font-headline text-brown mt-2">Review &amp; Submit</h1>

      {/* Capture summary */}
      <div className="rounded-xl bg-white shadow-sm p-4">
        <p className="text-xs text-brown/50 mb-3 uppercase tracking-wide">Captured</p>
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
        {capturedCount === 0 && (
          <p className="text-xs text-amber-600 mt-2">No images captured — demo mode will use pre-loaded samples.</p>
        )}
      </div>

      {/* Self-declaration (FR-4) */}
      <div className="rounded-xl bg-white shadow-sm p-4 flex flex-col gap-4">
        <p className="text-xs text-brown/50 uppercase tracking-wide">Tell us about your piece</p>
        <label className="flex flex-col gap-1">
          <span className="text-sm text-brown/60">Declared Weight (g)</span>
          <input type="number" placeholder="e.g. 10.5" value={weight}
            onChange={(e) => setWeight(e.target.value)}
            className="border border-brown/20 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-gold" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm text-brown/60">Karat / Stamp on piece</span>
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

      {error && <p className="text-red-600 text-sm text-center">{error}</p>}

      {/* Stage feedback */}
      {loading && stage && (
        <div className="flex items-center gap-3 text-brown/60 text-sm justify-center">
          <div className="w-4 h-4 rounded-full border-2 border-gold border-t-transparent animate-spin" />
          {stage}
        </div>
      )}

      <button onClick={handleSubmit} disabled={loading}
        className="min-touch w-full bg-brown text-ivory font-semibold rounded-xl py-4 text-lg shadow-md disabled:opacity-50 hover:bg-brown-dark transition-colors">
        {loading ? "Uploading…" : "Submit for Estimate"}
      </button>

      <button onClick={() => navigate("/capture")} className="text-brown/40 text-sm text-center underline">
        ← Retake photos
      </button>
    </div>
  );
}
