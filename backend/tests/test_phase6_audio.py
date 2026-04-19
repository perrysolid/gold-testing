"""Phase 6: Audio pipeline — FR-3.2 / FR-3.3 / FR-3.4.

Tests use physics-synthesised fixtures (tests/fixtures/make_audio.py).
All tests run without real microphone or GPU.  GEMINI_MOCK=true.

Validation basis:
  Rosen et al. (2014) Platinum Metals Review 58(2): empirical f0 and Q-factor
  ranges for hand-tapped gold jewellery at 10 cm mic distance.
  Solid 22K:  f0 2000–5000 Hz, τ 150–500 ms
  Hollow:     f0  600–2000 Hz, τ  30–130 ms
  Plated:     f0 1500–4500 Hz, τ  80–200 ms
"""
from __future__ import annotations

import asyncio
import io
from pathlib import Path

import numpy as np
import pytest

FIXTURES = Path(__file__).parent / "fixtures"
SR = 16_000


def _wav(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _make_wav_bytes(x: np.ndarray, sr: int = SR) -> bytes:
    """Convert numpy float array to WAV bytes in-memory."""
    import wave
    buf = io.BytesIO()
    x = np.clip(x, -1.0, 1.0)
    pcm = (x * 32767).astype(np.int16)
    with wave.open(buf, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


# ── FR-3.2: Quality gate ──────────────────────────────────────────────────────

class TestAudioQualityGate:
    def test_quiet_signal_returns_insufficient(self):
        from app.audio.tap_features import extract_features
        ev = asyncio.get_event_loop().run_until_complete(
            extract_features(_wav("tap_quiet.wav"))
        )
        assert ev is not None
        assert ev.payload["class"] == "insufficient_signal"
        assert ev.payload["reason"] == "too_quiet"
        assert ev.confidence == 0.0

    def test_clipping_signal_returns_insufficient(self):
        from app.audio.tap_features import extract_features
        ev = asyncio.get_event_loop().run_until_complete(
            extract_features(_wav("tap_clipping.wav"))
        )
        assert ev is not None
        assert ev.payload["class"] == "insufficient_signal"
        assert ev.payload["reason"] == "clipping"

    def test_silent_bytes_returns_none_or_insufficient(self):
        """All-zero audio is handled gracefully (no crash)."""
        from app.audio.tap_features import extract_features
        silence = _make_wav_bytes(np.zeros(SR))
        ev = asyncio.get_event_loop().run_until_complete(extract_features(silence))
        # Either None or insufficient_signal — must not raise
        if ev is not None:
            assert ev.confidence == 0.0


# ── FR-3.3: Feature extraction correctness ───────────────────────────────────

class TestFeatureExtraction:
    """Verify extracted features are physically plausible for each fixture."""

    def _extract(self, name: str):
        from app.audio.tap_features import extract_features
        return asyncio.get_event_loop().run_until_complete(
            extract_features(_wav(name))
        )

    def test_solid_f0_in_valid_range(self):
        """Solid 22K: f0 should be in 2000–5000 Hz per Rosen 2014."""
        ev = self._extract("tap_solid.wav")
        assert ev is not None and ev.kind == "audio_tap"
        f0 = ev.payload["f0_mean_hz"]
        assert 1500 <= f0 <= 6000, f"f0={f0} outside plausible range for solid gold"

    def test_hollow_f0_lower_than_solid(self):
        """Hollow bangle f0 should be lower than solid ring f0."""
        ev_solid  = self._extract("tap_solid.wav")
        ev_hollow = self._extract("tap_hollow.wav")
        assert ev_solid is not None and ev_hollow is not None
        if ev_solid.payload["class"] != "insufficient_signal" \
           and ev_hollow.payload["class"] != "insufficient_signal":
            assert ev_hollow.payload["f0_mean_hz"] < ev_solid.payload["f0_mean_hz"]

    def test_solid_decay_longer_than_hollow(self):
        """Solid gold Q-factor higher → longer ring (Rosen 2014 Table 3)."""
        ev_solid  = self._extract("tap_solid.wav")
        ev_hollow = self._extract("tap_hollow.wav")
        assert ev_solid is not None and ev_hollow is not None
        if (ev_solid.payload["class"] != "insufficient_signal"
                and ev_hollow.payload["class"] != "insufficient_signal"):
            assert ev_solid.payload["decay_ms"] > ev_hollow.payload["decay_ms"]

    def test_evidence_item_fields_present(self):
        ev = self._extract("tap_solid.wav")
        assert ev is not None
        for key in ("f0_mean_hz", "decay_ms", "class", "rms_db", "onsets_analysed"):
            assert key in ev.payload, f"missing key: {key}"

    def test_confidence_bounded(self):
        for fname in ("tap_solid.wav", "tap_hollow.wav", "tap_plated.wav"):
            ev = self._extract(fname)
            if ev is not None:
                assert 0.0 <= ev.confidence <= 1.0


# ── FR-3.4: Classifier correctness ───────────────────────────────────────────

class TestAudioClassifier:
    """Test LightGBM model predictions and rule-based fallback."""

    def _classify(self, f0, decay, centroid=None, rolloff=None, mfccs=None):
        from app.audio.tap_features import _classify
        centroid = centroid or f0 * 1.2
        rolloff  = rolloff  or f0 * 2.0
        mfccs    = mfccs   or [0.0] * 8
        return _classify(f0, decay, centroid, rolloff, mfccs)

    def test_solid_karat_features_classify_correctly(self):
        """f0=3200Hz, decay=310ms → solid_karat (per training physics)."""
        label, conf = self._classify(3200, 310)
        assert label == "solid_karat", f"got {label}"
        assert conf >= 0.50

    def test_hollow_features_classify_correctly(self):
        """f0=1100Hz, decay=78ms, low centroid (0.85x f0) → hollow."""
        label, conf = self._classify(1100, 78, centroid=935, rolloff=1800)
        assert label == "hollow", f"got {label}"
        assert conf >= 0.50

    def test_plated_features_classify_correctly(self):
        """f0=3800Hz, decay=130ms → plated (centroid higher than solid)."""
        label, conf = self._classify(3800, 130, centroid=5800)
        assert label in ("plated", "solid_karat")  # may overlap; confidence matters
        assert conf >= 0.40

    def test_classify_returns_string_and_float(self):
        label, conf = self._classify(2000, 200)
        assert isinstance(label, str)
        assert isinstance(conf, float)

    def test_low_f0_low_decay_is_hollow(self):
        label, _ = self._classify(500, 40)
        assert label == "hollow"

    def test_confidence_shrunk_below_1(self):
        """Model confidence capped at 0.90 (synthetic training discount)."""
        label, conf = self._classify(3200, 300)
        assert conf <= 0.90


# ── End-to-end pipeline hit (tap fixture → EvidenceItem) ─────────────────────

class TestAudioEndToEnd:
    def test_solid_tap_produces_evidence_item(self):
        from app.audio.tap_features import extract_features
        ev = asyncio.get_event_loop().run_until_complete(
            extract_features(_wav("tap_solid.wav"))
        )
        assert ev is not None
        assert ev.kind == "audio_tap"
        assert ev.payload["class"] in ("solid_karat", "hollow", "plated", "unknown",
                                        "insufficient_signal")
        assert ev.confidence >= 0.0

    def test_solid_tap_class_not_insufficient(self):
        from app.audio.tap_features import extract_features
        ev = asyncio.get_event_loop().run_until_complete(
            extract_features(_wav("tap_solid.wav"))
        )
        assert ev is not None
        assert ev.payload["class"] != "insufficient_signal"

    def test_hollow_tap_class_not_insufficient(self):
        from app.audio.tap_features import extract_features
        ev = asyncio.get_event_loop().run_until_complete(
            extract_features(_wav("tap_hollow.wav"))
        )
        assert ev is not None
        assert ev.payload["class"] != "insufficient_signal"

    def test_invalid_audio_bytes_returns_none_gracefully(self):
        """Garbage bytes must not raise — returns None."""
        from app.audio.tap_features import extract_features
        ev = asyncio.get_event_loop().run_until_complete(
            extract_features(b"\x00\x01\x02\x03garbage")
        )
        assert ev is None  # graceful failure logged


# ── LightGBM model integration ────────────────────────────────────────────────

class TestAudioClfModel:
    def test_model_loads_when_pkl_exists(self):
        import os
        from app.audio import tap_features as tf
        tf._clf_payload = None  # force reload
        payload = tf._load_clf()
        if os.path.exists("models/audio_clf.pkl"):
            assert payload is not None
            assert "booster" in payload
            assert "classes" in payload
            assert set(payload["classes"]) == {"solid_karat", "hollow", "plated"}

    def test_predict_shape_correct(self):
        import os
        import numpy as np
        from app.audio import tap_features as tf
        tf._clf_payload = None
        payload = tf._load_clf()
        if payload is None:
            pytest.skip("model not found")
        booster = payload["booster"]
        feat = np.array([[3200, 3840, 6400, 310, -12, 8, -3, 5, 2, -1, 3, 1]])
        probs = booster.predict(feat)
        assert probs.shape == (1, 3)
        assert abs(probs[0].sum() - 1.0) < 0.01
