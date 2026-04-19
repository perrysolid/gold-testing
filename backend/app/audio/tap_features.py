"""FR-3: Audio tap-test feature extraction + LightGBM classifier.

FR-3.2: 16 kHz mono, reject if RMS too quiet or clipping.
FR-3.3: Per-onset f0 (pyin), spectral centroid, rolloff, MFCCs, decay time.
FR-3.4: LightGBM classifier → solid_karat / hollow / plated / unknown.
         Falls back to rule-based when model not loaded.

Feature vector (12 dims, must match scripts/train_audio_model.py):
  [f0_hz, centroid_hz, rolloff_hz, decay_ms, mfcc_0..7]

Physics reference for class boundaries:
  solid_karat: f0 2000–5000 Hz, τ 150–500 ms  (Rosen et al. 2014)
  hollow:      f0  600–2000 Hz, τ  30–130 ms
  plated:      f0 1500–4500 Hz, τ  80–200 ms  (brass/Cu substrate)
"""
from __future__ import annotations

import os
import pickle
import uuid
from typing import Optional

import structlog

from app.assess.schemas import EvidenceItem

logger = structlog.get_logger()

TARGET_SR = 16_000
ONSET_WINDOW_SAMPLES = TARGET_SR // 2   # 500 ms
FEATURE_ORDER = ["f0_hz", "centroid_hz", "rolloff_hz", "decay_ms", *[f"mfcc_{i}" for i in range(8)]]

_clf_payload: Optional[dict] = None


def _load_clf() -> Optional[dict]:
    global _clf_payload
    if _clf_payload is None:
        from app.config import get_settings
        path = get_settings().audio_clf_model
        if os.path.exists(path):
            with open(path, "rb") as f:
                _clf_payload = pickle.load(f)
            logger.info("audio.clf_loaded", path=path,
                        classes=_clf_payload.get("classes"))
        else:
            logger.warning("audio.clf_not_found", path=path, fallback="rule_based")
    return _clf_payload


async def extract_features(audio_bytes: bytes) -> Optional[EvidenceItem]:
    """FR-3.3/3.4: Extract tap features and classify material."""
    try:
        import io
        import numpy as np
        import librosa  # type: ignore[import]

        y, sr = librosa.load(io.BytesIO(audio_bytes), sr=TARGET_SR, mono=True)

        # FR-3.2: quality gate
        # Browser WebAudio recordings are often lower amplitude than -50 dB,
        # so use a more lenient gate (-62 dB lower bound, -1 dB upper).
        rms_db = float(20 * np.log10(np.sqrt(np.mean(y ** 2)) + 1e-9))
        if rms_db < -62:
            return _insufficient("too_quiet", rms_db)
        if rms_db > -1:
            return _insufficient("clipping", rms_db)

        onset_frames = librosa.onset.onset_detect(y=y, sr=sr, units="samples")
        if len(onset_frames) == 0:
            return _insufficient("no_onset", rms_db)

        features_per_onset: list[dict] = []
        for onset in onset_frames[:5]:
            window = y[onset: onset + ONSET_WINDOW_SAMPLES]
            if len(window) < ONSET_WINDOW_SAMPLES // 4:
                continue

            f0_arr, _, _ = librosa.pyin(window, fmin=200, fmax=8000, sr=sr)  # type: ignore[misc]
            f0_mean = float(np.nanmean(f0_arr)) if f0_arr is not None and not np.all(np.isnan(f0_arr)) else 0.0

            centroid = float(librosa.feature.spectral_centroid(y=window, sr=sr).mean())
            rolloff  = float(librosa.feature.spectral_rolloff(y=window, sr=sr).mean())
            mfccs    = librosa.feature.mfcc(y=window, sr=sr, n_mfcc=13).mean(axis=1).tolist()

            hop = 256
            rms_env   = librosa.feature.rms(y=window, hop_length=hop)[0]
            decay_ms  = _estimate_decay(rms_env, hop, sr)

            features_per_onset.append({
                "f0_hz":       round(f0_mean, 1),
                "centroid_hz": round(centroid, 1),
                "rolloff_hz":  round(rolloff, 1),
                "mfccs":       [round(m, 2) for m in mfccs[:8]],
                "decay_ms":    round(decay_ms, 1),
            })

        if not features_per_onset:
            return _insufficient("no_valid_onset", rms_db)

        f0_mean    = float(np.mean([f["f0_hz"]    for f in features_per_onset]))
        decay_mean = float(np.mean([f["decay_ms"] for f in features_per_onset]))
        centroid_m = float(np.mean([f["centroid_hz"] for f in features_per_onset]))
        rolloff_m  = float(np.mean([f["rolloff_hz"]  for f in features_per_onset]))
        mfcc_mean  = np.mean([f["mfccs"] for f in features_per_onset], axis=0).tolist()

        label, conf = _classify(f0_mean, decay_mean, centroid_m, rolloff_m, mfcc_mean)

        return EvidenceItem(
            id=f"ev_{uuid.uuid4().hex[:8]}",
            kind="audio_tap",
            payload={
                "f0_mean_hz":    round(f0_mean, 1),
                "decay_ms":      round(decay_mean, 1),
                "centroid_hz":   round(centroid_m, 1),
                "class":         label,
                "rms_db":        round(rms_db, 1),
                "onsets_analysed": len(features_per_onset),
            },
            confidence=conf,
        )

    except Exception as e:
        logger.warning("audio.feature_extraction_failed", error=str(e))
        return None


def _classify(
    f0_hz: float,
    decay_ms: float,
    centroid_hz: float,
    rolloff_hz: float,
    mfccs: list[float],
) -> tuple[str, float]:
    """Use LightGBM model if available; rule-based fallback."""
    import numpy as np

    payload = _load_clf()
    if payload is not None:
        try:
            booster = payload["booster"]
            classes = payload["classes"]
            feat = np.array([[f0_hz, centroid_hz, rolloff_hz, decay_ms, *mfccs[:8]]])
            probs = booster.predict(feat)[0]   # shape (n_classes,)
            idx   = int(probs.argmax())
            conf  = float(probs[idx])
            # Shrink confidence slightly for uncertainty — model trained on synthetics
            conf  = round(min(conf * 0.88, 0.90), 3)
            return classes[idx], conf
        except Exception as e:
            logger.warning("audio.clf_inference_failed", error=str(e))

    # Rule-based fallback (Rosen et al. 2014 empirical thresholds)
    if f0_hz < 1000 or decay_ms < 80:
        return "hollow", 0.60
    if 2000 <= f0_hz <= 5000 and 150 <= decay_ms <= 500:
        return "solid_karat", 0.68
    if 1500 <= f0_hz <= 4500 and 80 <= decay_ms <= 200:
        return "plated", 0.55
    return "unknown", 0.35


def _estimate_decay(rms_env: "np.ndarray", hop: int, sr: int) -> float:  # type: ignore[name-defined]
    import numpy as np
    if rms_env.max() == 0:
        return 0.0
    norm = rms_env / rms_env.max()
    below = np.where(norm < (1 / np.e))[0]
    if len(below) == 0:
        return float(len(norm) * hop / sr * 1000)
    return float(below[0] * hop / sr * 1000)


def _insufficient(reason: str, rms_db: float) -> EvidenceItem:
    return EvidenceItem(
        id=f"ev_{uuid.uuid4().hex[:8]}",
        kind="audio_tap",
        payload={"class": "insufficient_signal", "reason": reason, "rms_db": round(rms_db, 1)},
        confidence=0.0,
    )
