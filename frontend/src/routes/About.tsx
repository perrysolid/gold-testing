// US-D2: Architecture page for judges
import { useNavigate } from "react-router-dom";

const STACK = [
  { layer: "Frontend", tech: "React 18 + Vite PWA + TailwindCSS", icon: "⚛️" },
  { layer: "Backend", tech: "FastAPI + Python 3.11 (port 8000)", icon: "🐍" },
  { layer: "Vision", tech: "YOLOv8n + SAM2-tiny + MiDaS + PaddleOCR", icon: "👁️" },
  { layer: "Audio", tech: "librosa + rule-based tap classifier", icon: "🎵" },
  { layer: "Fusion", tech: "Weighted evidence + LightGBM + sklearn RF", icon: "🧮" },
  { layer: "LLM", tech: "Gemini 2.5 Flash (OCR fallback + explanation)", icon: "✨" },
  { layer: "Storage", tech: "SQLite/Postgres + MinIO (S3-compatible)", icon: "🗄️" },
];

export default function About() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-ivory p-6 max-w-2xl mx-auto">
      <button onClick={() => navigate(-1)} className="text-brown/50 text-sm mb-6 hover:text-brown">← Back</button>
      <h1 className="text-3xl font-headline text-brown mb-2">How Aurum Works</h1>
      <p className="text-brown/60 mb-6 text-sm">
        Multimodal gold jewellery assessment: vision + audio + self-declaration → lending decision.
        All models are open-source. Gemini is used only for OCR fallback and explanation text.
      </p>

      {/* Stack table */}
      <div className="rounded-xl bg-white shadow-sm overflow-hidden mb-6">
        {STACK.map((row, i) => (
          <div key={row.layer} className={`flex items-start gap-3 p-4 ${i > 0 ? "border-t border-brown/5" : ""}`}>
            <span className="text-xl mt-0.5">{row.icon}</span>
            <div>
              <p className="font-semibold text-brown text-sm">{row.layer}</p>
              <p className="text-brown/50 text-xs">{row.tech}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Data flow */}
      <div className="rounded-xl bg-brown/5 p-4 text-xs text-brown/70 font-mono leading-6">
        Camera → Compress → Upload<br/>
        → YOLOv8 classify → SAM2 segment<br/>
        → Hallmark detect → PaddleOCR → Gemini fallback<br/>
        → MiDaS depth + ArUco scale → Weight band<br/>
        → Audio f0/decay → Solid/hollow class<br/>
        → Fusion engine → YAML decision rules<br/>
        → LTV calc → Gemini explanation → PDF
      </div>

      <div className="mt-6 text-xs text-brown/30 space-y-1">
        <p>YOLOv8 — AGPL-3.0 (Ultralytics) · SAM2 — Apache 2.0 (Meta AI)</p>
        <p>MiDaS — MIT (Intel ISL) · PaddleOCR — Apache 2.0 (PaddlePaddle)</p>
        <p>librosa — ISC · Gemini API — commercial (Google)</p>
      </div>
    </div>
  );
}
