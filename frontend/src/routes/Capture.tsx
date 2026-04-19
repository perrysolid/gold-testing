// FR-2.1–FR-2.5: 3-step camera capture with live quality chips + compression
import { useCallback, useRef, useState } from "react";
import Webcam from "react-webcam";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import QualityChip from "../components/QualityChip";
import CameraGuide from "../components/CameraGuide";
import HallmarkGuide from "../components/HallmarkGuide";
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

type CaptureStep = {
  key: "image_top" | "image_side" | "image_hallmark";
  labelKey: string;
  hintKey: string;
};

const STEPS: CaptureStep[] = [
  { key: "image_top",      labelKey: "capture.step_top",      hintKey: "capture.tip_top" },
  { key: "image_side",     labelKey: "capture.step_side",     hintKey: "capture.tip_side" },
  { key: "image_hallmark", labelKey: "capture.step_hallmark", hintKey: "capture.tip_hallmark" },
];

// Returns the right sample image for this step + item type
function getSampleImage(stepKey: string, type: string): string {
  if (stepKey === "image_hallmark") return "/demo/images/hallmark_916.jpg";
  const view = stepKey === "image_top" ? "top" : "side";
  const item = ["ring", "chain", "bangle", "earring", "pendant", "coin"].includes(type) ? type : "ring";
  return `/demo/images/${item}_${view}.jpg`;
}

type Quality = QualityResult;

export default function Capture() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const webcamRef = useRef<Webcam>(null);
  const [stepIdx, setStepIdx] = useState(0);
  const [quality, setQuality] = useState<Quality | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [capturing, setCapturing] = useState(false);
  const [cameraError, setCameraError] = useState(false);
  const { setCaptures, itemType } = useCaptureStore();

  const step = STEPS[stepIdx];

  const handleUserMedia = () => setCameraError(false);
  const handleCameraError = () => setCameraError(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const processImageFile = async (file: File) => {
    setCapturing(true);
    try {
      const compressed = await compressImage(file);
      // FR-2.4: server-side check preferred (Laplacian sharpness); client fallback if offline
      const qual = (await serverQualityCheck(compressed)) ?? (await checkImageQuality(compressed));
      setQuality(qual);

      const url = URL.createObjectURL(compressed);
      setPreview(url);

      // Store compressed blob in Zustand for upload in Review
      const buf = await compressed.arrayBuffer();
      setCaptures(step.key, new Uint8Array(buf));
    } finally {
      setCapturing(false);
    }
  };

  const capture = useCallback(async () => {
    if (!webcamRef.current) return;
    const screenshot = webcamRef.current.getScreenshot({ width: 1600, height: 1200 });
    if (!screenshot) return;

    // Convert data-URL → File for compression
    const res = await fetch(screenshot);
    const blob = await res.blob();
    const file = new File([blob], `${step.key}.jpg`, { type: "image/jpeg" });
    await processImageFile(file);
  }, [step.key, setCaptures]);

  const loadSample = async () => {
    const url = getSampleImage(step.key, itemType || "ring");
    setCapturing(true);
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const file = new File([blob], `${step.key}_sample.jpg`, { type: "image/jpeg" });
      await processImageFile(file);
    } catch (e) {
      console.warn("Sample load failed:", url, e);
    } finally {
      setCapturing(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await processImageFile(file);
    }
  };

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
        <span className="text-ivory text-sm font-medium">{t(step.labelKey)}</span>
        <span className="text-white/40 text-xs">{stepIdx + 1} / {STEPS.length}</span>
      </div>

      {/* Camera / Preview */}
      <div className="flex-1 relative overflow-hidden">
        {/* Preview always takes priority regardless of camera state */}
        {preview ? (
          <img src={preview} alt="Captured" className="w-full h-full object-cover object-center" />
        ) : !cameraError ? (
          <>
            <Webcam
              ref={webcamRef}
              screenshotFormat="image/jpeg"
              videoConstraints={videoConstraints}
              onUserMedia={handleUserMedia}
              onUserMediaError={handleCameraError}
              className="w-full h-full object-cover object-center"
            />
            <CameraGuide itemType={itemType || "ring"} />
          </>
        ) : (
          <div className="w-full h-64 flex flex-col items-center justify-center gap-3 bg-brown/10">
            <span className="text-4xl">📷</span>
            <p className="text-brown/60 text-sm text-center px-6">{t("common.error")}</p>
          </div>
        )}
      </div>

      {/* Quality chips */}
      {quality && (
        <div className="bg-black/80 px-4 py-2 flex flex-col gap-2">
          <div className="flex gap-2 flex-wrap">
            <QualityChip label={t("capture.quality_bright")} ok={quality.bright_ok} />
            <QualityChip label={t("capture.quality_sharp")} ok={quality.sharp_ok} />
            <QualityChip label={t("capture.quality_frame")} ok={quality.occupancy_ok} />
            <QualityChip label="Gold item" ok={quality.jewellery_ok} />
          </div>
          {quality.jewellery_ok === false && (
            <p className="text-amber-400 text-xs text-center">
              No gold/silver jewellery detected. Please photograph your jewellery item, not a person or other object.
            </p>
          )}
        </div>
      )}

      {/* Hallmark guide — only on hallmark step, above camera controls */}
      {step.key === "image_hallmark" && (
        <div className="bg-brown px-4 pt-3">
          <HallmarkGuide compact />
        </div>
      )}

      {/* Bottom controls */}
      <div className="bg-brown px-4 py-4 flex flex-col gap-3">
        <p className="text-white/60 text-xs text-center">{t(step.hintKey)}</p>

        {!preview ? (
          <div className="flex flex-col gap-2">
            <div className="flex gap-2">
              <button
                onClick={capture}
                disabled={capturing || cameraError}
                className="min-touch flex-1 bg-gold text-brown-dark font-bold rounded-xl py-4 text-lg disabled:opacity-40"
              >
                {capturing ? t("capture.analysing") : "📸 " + t("capture.title")}
              </button>
              <input
                type="file"
                accept="image/*"
                className="hidden"
                ref={fileInputRef}
                onChange={handleFileUpload}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={capturing}
                className="min-touch w-14 bg-white/10 text-gold rounded-xl py-4 flex items-center justify-center disabled:opacity-40 border border-white/20"
                title="Upload photo"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
              </button>
            </div>
            {/* Demo: load pre-made gold sample for this step */}
            <button
              onClick={loadSample}
              disabled={capturing}
              className="min-touch w-full bg-white/8 border border-gold/30 text-gold/80 rounded-xl py-2.5 text-xs font-medium hover:bg-gold/10 transition-colors disabled:opacity-40"
            >
              ⚡ Load sample gold image (demo)
            </button>
          </div>
        ) : (
          <div className="flex gap-3">
            <button onClick={retake}
              className="min-touch flex-1 border border-white/20 text-ivory rounded-xl py-3 font-medium">
              {t("capture.retake")}
            </button>
            <button onClick={next}
              disabled={quality !== null && quality.jewellery_ok === false}
              className="min-touch flex-2 flex-grow bg-gold text-brown-dark rounded-xl py-3 font-bold disabled:opacity-40">
              {stepIdx < STEPS.length - 1 ? t("capture.next") + " →" : t("capture.submit")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
