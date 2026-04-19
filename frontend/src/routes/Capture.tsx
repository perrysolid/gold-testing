// FR-2.1–FR-2.5: 3-step camera capture with live quality chips + compression
import { useCallback, useRef, useState } from "react";
import Webcam from "react-webcam";
import { useNavigate } from "react-router-dom";
import QualityChip from "../components/QualityChip";
import CameraGuide from "../components/CameraGuide";
import { compressImage } from "../lib/compress";
import { checkImageQuality, QualityResult } from "../lib/quality";
import { useCaptureStore } from "../lib/store";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function serverQualityCheck(blob: Blob): Promise<QualityResult | null> {
  try {
    const form = new FormData();
    form.append("file", blob, "capture.jpg");
    const r = await fetch(`${BASE}/assess/quality-check`, { method: "POST", body: form });
    if (!r.ok) return null;
    return await r.json() as QualityResult;
  } catch {
    return null;
  }
}

type CaptureStep = { key: "image_top" | "image_side" | "image_hallmark"; label: string; hint: string };

const STEPS: CaptureStep[] = [
  { key: "image_top",      label: "Top View",        hint: "Place jewellery flat. Ensure good lighting." },
  { key: "image_side",     label: "Side View",        hint: "Tilt the piece to show thickness." },
  { key: "image_hallmark", label: "Hallmark Close-up", hint: "Zoom in on the stamp/hallmark area." },
];

type Quality = { bright_ok: boolean; sharp_ok: boolean; occupancy_ok: boolean; overall_ok: boolean };

export default function Capture() {
  const navigate = useNavigate();
  const webcamRef = useRef<Webcam>(null);
  const [stepIdx, setStepIdx] = useState(0);
  const [quality, setQuality] = useState<Quality | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [capturing, setCapturing] = useState(false);
  const [cameraError, setCameraError] = useState(false);
  const { setCaptures, itemType } = useCaptureStore();

  const step = STEPS[stepIdx];

  // FR-2.4: real-time quality check on camera frame
  const handleUserMedia = () => setCameraError(false);
  const handleCameraError = () => setCameraError(true);

  const capture = useCallback(async () => {
    if (!webcamRef.current) return;
    setCapturing(true);
    const screenshot = webcamRef.current.getScreenshot({ width: 1600, height: 1200 });
    if (!screenshot) { setCapturing(false); return; }

    // Convert data-URL → File for compression
    const res = await fetch(screenshot);
    const blob = await res.blob();
    const file = new File([blob], `${step.key}.jpg`, { type: "image/jpeg" });
    const compressed = await compressImage(file);
    // FR-2.4: server-side check preferred (Laplacian sharpness); client fallback if offline
    const qual = (await serverQualityCheck(compressed)) ?? (await checkImageQuality(compressed));
    setQuality(qual);

    const url = URL.createObjectURL(compressed);
    setPreview(url);
    setCapturing(false);

    // Store compressed blob in Zustand for upload in Review
    const buf = await compressed.arrayBuffer();
    setCaptures(step.key, new Uint8Array(buf));
  }, [step.key, setCaptures]);

  const retake = () => { setPreview(null); setQuality(null); };

  const next = () => {
    if (stepIdx < STEPS.length - 1) {
      setStepIdx((i) => i + 1);
      setPreview(null);
      setQuality(null);
    } else {
      navigate("/audio");
    }
  };

  const videoConstraints = {
    width: { ideal: 1920 },
    height: { ideal: 1080 },
    facingMode: { ideal: "environment" }, // rear camera on mobile
  };

  return (
    <div className="min-h-screen bg-black flex flex-col">
      {/* Header */}
      <div className="bg-brown px-4 py-3 flex items-center justify-between">
        <div className="flex gap-2">
          {STEPS.map((s, i) => (
            <div key={s.key} className={`w-8 h-1 rounded-full ${i <= stepIdx ? "bg-gold" : "bg-white/20"}`} />
          ))}
        </div>
        <span className="text-ivory text-sm font-medium">{step.label}</span>
        <span className="text-white/40 text-xs">{stepIdx + 1} / {STEPS.length}</span>
      </div>

      {/* Camera / Preview */}
      <div className="flex-1 relative overflow-hidden">
        {!cameraError ? (
          <>
            {!preview && (
              <Webcam
                ref={webcamRef}
                screenshotFormat="image/jpeg"
                videoConstraints={videoConstraints}
                onUserMedia={handleUserMedia}
                onUserMediaError={handleCameraError}
                className="w-full h-full object-cover"
                style={{ maxHeight: "calc(100vh - 200px)" }}
              />
            )}
            {preview && (
              <img src={preview} alt="Captured" className="w-full h-full object-cover" style={{ maxHeight: "calc(100vh - 200px)" }} />
            )}
            {!preview && <CameraGuide itemType={itemType || "ring"} />}
          </>
        ) : (
          <div className="w-full h-64 flex flex-col items-center justify-center gap-3 bg-brown/10">
            <span className="text-4xl">📷</span>
            <p className="text-brown/60 text-sm text-center px-6">Camera not available.<br/>Allow camera access or use demo mode.</p>
            <button onClick={() => navigate("/result/demo-genuine-22k-chain")}
              className="text-gold text-sm underline">Use demo instead</button>
          </div>
        )}
      </div>

      {/* Quality chips */}
      {quality && (
        <div className="bg-black/80 px-4 py-2 flex gap-2 flex-wrap">
          <QualityChip label="Brightness" ok={quality.bright_ok} />
          <QualityChip label="Sharp" ok={quality.sharp_ok} />
          <QualityChip label="In Frame" ok={quality.occupancy_ok} />
        </div>
      )}

      {/* Bottom controls */}
      <div className="bg-brown px-4 py-4 flex flex-col gap-3">
        <p className="text-white/60 text-xs text-center">{step.hint}</p>

        {!preview ? (
          <button
            onClick={capture}
            disabled={capturing || cameraError}
            className="min-touch w-full bg-gold text-brown-dark font-bold rounded-xl py-4 text-lg disabled:opacity-40"
          >
            {capturing ? "Capturing…" : "📸 Capture"}
          </button>
        ) : (
          <div className="flex gap-3">
            <button onClick={retake}
              className="min-touch flex-1 border border-white/20 text-ivory rounded-xl py-3 font-medium">
              Retake
            </button>
            <button onClick={next}
              disabled={quality !== null && !quality.overall_ok}
              className="min-touch flex-2 flex-grow bg-gold text-brown-dark rounded-xl py-3 font-bold disabled:opacity-40">
              {stepIdx < STEPS.length - 1 ? "Next →" : "Continue"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
