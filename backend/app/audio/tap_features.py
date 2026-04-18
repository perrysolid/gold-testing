"""FR-3: Audio tap-test feature extraction + rule-based classifier.

FR-3.2: 16 kHz mono, reject if RMS too quiet or clipping.
FR-3.3: Per-onset f0, spectral centroid, MFCCs, decay time.
FR-3.4: Rule-based classifier (solid_karat / hollow / plated / unknown).
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog

from app.assess.schemas import EvidenceItem

logger = structlog.get_logger()

TARGET_SR = 16_000
ONSET_WINDOW_SAMPLES = TARGET_SR // 2  # 500 ms


async def extract_features(audio_bytes: bytes) -> Optional[EvidenceItem]:
    """FR-3.3/3.4: Extract tap features and classify material."""
    try:
        import io
        import numpy as np
        import librosa  # type: ignore[import]

        y, sr = librosa.load(io.BytesIO(audio_bytes), sr=TARGET_SR, mono=True)

        # FR-3.2: RMS check
        rms_db = float(20 * np.log10(np.sqrt(np.mean(y ** 2)) + 1e-9))
        if rms_db < -50:
            return _insufficient("too_quiet", rms_db)
        if rms_db > -3:
            return _insufficient("clipping", rms_db)

        # Onset detection
        onset_frames = librosa.onset.onset_detect(y=y, sr=sr, units="samples")
        if len(onset_frames) == 0:
            return _insufficient("no_onset", rms_db)

        features_per_onset = []
        for onset in onset_frames[:5]:
            window = y[onset : onset + ONSET_WINDOW_SAMPLES]
            if len(window) < ONSET_WINDOW_SAMPLES // 4:
                continue

            f0_arr, _, _ = librosa.pyin(window, fmin=200, fmax=8000, sr=sr)  # type: ignore[misc]
            f0_mean = float(np.nanmean(f0_arr)) if f0_arr is not None else 0.0

            centroid = float(librosa.feature.spectral_centroid(y=window, sr=sr).mean())
            rolloff = float(librosa.feature.spectral_rolloff(y=window, sr=sr).mean())
            mfccs = librosa.feature.mfcc(y=window, sr=sr, n_mfcc=13).mean(axis=1).tolist()

            # Decay: fit exponential to RMS envelope
            hop = 256
            rms_env = librosa.feature.rms(y=window, hop_length=hop)[0]
            decay_ms = _estimate_decay(rms_env, hop, sr)

            features_per_onset.append({
                "f0_hz": round(f0_mean, 1),
                "centroid_hz": round(centroid, 1),
                "rolloff_hz": round(rolloff, 1),
                "mfccs": [round(m, 2) for m in mfccs],
                "decay_ms": round(decay_ms, 1),
            })

        if not features_per_onset:
            return _insufficient("no_valid_onset", rms_db)

        f0_mean = float(np.mean([f["f0_hz"] for f in features_per_onset]))
        decay_mean = float(np.mean([f["decay_ms"] for f in features_per_onset]))

        label, conf = _classify(f0_mean, decay_mean)

        return EvidenceItem(
            id=f"ev_{uuid.uuid4().hex[:8]}",
            kind="audio_tap",
            payload={
                "f0_mean_hz": round(f0_mean, 1),
                "decay_ms": round(decay_mean, 1),
                "class": label,
                "rms_db": round(rms_db, 1),
                "onsets_analysed": len(features_per_onset),
            },
            confidence=conf,
        )

    except Exception as e:
        logger.warning("audio.feature_extraction_failed", error=str(e))
        return None


def _estimate_decay(rms_env: "np.ndarray", hop: int, sr: int) -> float:  # type: ignore[name-defined]
    import numpy as np
    if rms_env.max() == 0:
        return 0.0
    norm = rms_env / rms_env.max()
    # Time until RMS drops to 1/e
    below = np.where(norm < (1 / np.e))[0]
    if len(below) == 0:
        return float(len(norm) * hop / sr * 1000)
    return float(below[0] * hop / sr * 1000)


def _classify(f0_hz: float, decay_ms: float) -> tuple[str, float]:
    """FR-3.4: Rule-based heuristic classifier."""
    if f0_hz < 1000 or decay_ms < 80:
        return "hollow", 0.65
    if 2000 <= f0_hz <= 5000 and 150 <= decay_ms <= 400:
        return "solid_karat", 0.72
    return "unknown", 0.40


def _insufficient(reason: str, rms_db: float) -> EvidenceItem:
    return EvidenceItem(
        id=f"ev_{uuid.uuid4().hex[:8]}",
        kind="audio_tap",
        payload={"class": "insufficient_signal", "reason": reason, "rms_db": round(rms_db, 1)},
        confidence=0.0,
    )
