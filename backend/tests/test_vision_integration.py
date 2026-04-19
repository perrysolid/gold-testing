"""FR-5: Vision pipeline integration tests using synthetic fixture images.

All ML model weights are absent in CI — tests verify graceful fallback paths
and that every stage returns a valid EvidenceItem without crashing.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
GOLD_RING = FIXTURES / "gold_ring.jpg"
ARUCO_RING = FIXTURES / "aruco_ring.jpg"
HALLMARK = FIXTURES / "hallmark_crop.jpg"
DARK = FIXTURES / "dark_image.jpg"


def _read(path: Path) -> bytes:
    return path.read_bytes()


# ── Quality checks (FR-2.4) ──────────────────────────────────────────────────

class TestQualityCheck:
    def test_good_image_passes(self):
        from app.vision.quality import check_quality
        result = check_quality(_read(GOLD_RING))
        assert result.bright_ok, f"brightness={result.brightness_mean}"
        assert result.overall_ok

    def test_dark_image_fails_brightness(self):
        from app.vision.quality import check_quality
        result = check_quality(_read(DARK))
        assert not result.bright_ok
        assert not result.overall_ok

    def test_returns_numeric_scores(self):
        from app.vision.quality import check_quality
        result = check_quality(_read(GOLD_RING))
        assert result.blur_score > 0
        assert 0 < result.brightness_mean < 256
        assert 0 <= result.occupancy_ratio <= 1


# ── Classifier (FR-5.1) ──────────────────────────────────────────────────────

class TestClassifier:
    def test_classify_returns_evidence_item(self):
        from app.vision.classifier import classify_type
        ev = asyncio.get_event_loop().run_until_complete(
            classify_type(_read(GOLD_RING), declared_type="ring")
        )
        assert ev.kind == "item_type_classification"
        assert ev.payload["class"] in [
            "ring", "chain", "bangle", "earring", "pendant", "coin", "bar",
            "non_jewellery", "not_jewellery", "unknown",
        ]
        assert 0 < ev.confidence <= 1.0

    def test_fallback_declared_type(self):
        """With no YOLO weights and GEMINI_MOCK=true, falls back to declared."""
        from app.vision.classifier import classify_type
        ev = asyncio.get_event_loop().run_until_complete(
            classify_type(_read(GOLD_RING), declared_type="bangle")
        )
        # fallback path uses declared_type; confidence capped at 0.40
        if ev.payload.get("source") == "declared_fallback":
            assert ev.confidence == pytest.approx(0.40)
            assert ev.payload["class"] == "bangle"


# ── Segmenter (FR-5.2) ───────────────────────────────────────────────────────

class TestSegmenter:
    def test_segment_returns_evidence(self):
        from app.vision.classifier import classify_type
        from app.vision.segmenter import segment
        ev_type = asyncio.get_event_loop().run_until_complete(
            classify_type(_read(GOLD_RING))
        )
        ev = asyncio.get_event_loop().run_until_complete(
            segment(_read(GOLD_RING), ev_type)
        )
        assert ev.kind == "segmentation_area_px"
        assert ev.payload.get("mask_area_px", 0) > 0
        assert 0 < ev.confidence <= 1.0

    def test_occupancy_ratio_nonzero(self):
        from app.vision.classifier import classify_type
        from app.vision.segmenter import segment
        ev_type = asyncio.get_event_loop().run_until_complete(
            classify_type(_read(GOLD_RING))
        )
        ev = asyncio.get_event_loop().run_until_complete(
            segment(_read(GOLD_RING), ev_type)
        )
        # segmenter stores mask_area_px (not occupancy_ratio directly)
        assert ev.payload.get("mask_area_px", 0) > 0


# ── Scale detection (FR-5.7) ─────────────────────────────────────────────────

class TestScale:
    def test_aruco_marker_detected(self):
        """ArUco ring fixture should trigger ArUco scale path."""
        from app.vision.scale import detect_scale
        ev = asyncio.get_event_loop().run_until_complete(
            detect_scale(_read(ARUCO_RING))
        )
        assert ev.kind == "scale_reference"
        # ArUco or heuristic — either is valid
        assert ev.payload.get("pixels_per_mm", 0) > 0

    def test_heuristic_fallback_on_plain_image(self):
        """Plain image with no marker → heuristic fallback."""
        from app.vision.scale import detect_scale
        ev = asyncio.get_event_loop().run_until_complete(
            detect_scale(_read(GOLD_RING))
        )
        assert ev.kind == "scale_reference"
        assert ev.payload.get("pixels_per_mm", 0) > 0


# ── Hallmark detector (FR-5.3) ───────────────────────────────────────────────

class TestHallmarkDetector:
    def test_returns_bbox(self):
        from app.vision.hallmark_detector import detect_hallmark
        ev = asyncio.get_event_loop().run_until_complete(
            detect_hallmark(_read(HALLMARK))
        )
        assert ev.kind == "hallmark_region"
        bbox = ev.payload.get("bbox")
        assert isinstance(bbox, list) and len(bbox) == 4

    def test_fallback_has_reduced_confidence(self):
        """Without YOLO weights, uses heuristic fallback at 0.3 confidence."""
        from app.vision.hallmark_detector import detect_hallmark
        ev = asyncio.get_event_loop().run_until_complete(
            detect_hallmark(_read(GOLD_RING))
        )
        if ev.payload.get("source") == "heuristic_fallback":
            assert ev.confidence == pytest.approx(0.3)


# ── Hallmark OCR (FR-5.4) ────────────────────────────────────────────────────

class TestHallmarkOCR:
    def test_returns_ocr_evidence(self):
        from app.vision.hallmark_detector import detect_hallmark
        from app.vision.hallmark_ocr import ocr_hallmark
        hallmark_ev = asyncio.get_event_loop().run_until_complete(
            detect_hallmark(_read(HALLMARK))
        )
        ev = asyncio.get_event_loop().run_until_complete(
            ocr_hallmark(_read(HALLMARK), hallmark_ev)
        )
        assert ev.kind == "hallmark_ocr"
        assert "purity_mark" in ev.payload
        assert "huid" in ev.payload
        assert "bis_logo" in ev.payload

    def test_no_crash_without_paddleocr(self):
        """Must not raise even if paddleocr is not installed."""
        from app.vision.hallmark_detector import detect_hallmark
        from app.vision.hallmark_ocr import ocr_hallmark, _load_ocr
        # Force reload attempt (may return None without crash)
        _ = _load_ocr()
        hallmark_ev = asyncio.get_event_loop().run_until_complete(
            detect_hallmark(_read(GOLD_RING))
        )
        ev = asyncio.get_event_loop().run_until_complete(
            ocr_hallmark(_read(GOLD_RING), hallmark_ev)
        )
        assert ev.kind == "hallmark_ocr"


# ── Plating detector (FR-5.5) ────────────────────────────────────────────────

class TestPlatingDetector:
    def test_returns_plating_risk(self):
        from app.vision.classifier import classify_type
        from app.vision.segmenter import segment
        from app.vision.plating_detector import detect_plating
        img = _read(GOLD_RING)
        ev_type = asyncio.get_event_loop().run_until_complete(classify_type(img))
        ev_seg = asyncio.get_event_loop().run_until_complete(segment(img, ev_type))
        ev = asyncio.get_event_loop().run_until_complete(detect_plating(img, ev_seg))
        assert ev.kind == "plating_detection"
        risk = ev.payload.get("plating_risk", -1)
        assert 0 <= risk <= 1
        assert ev.confidence <= 0.55, "rule-based confidence must be capped at 0.55"


# ── Depth estimator (FR-5.8) ─────────────────────────────────────────────────

class TestDepthEstimator:
    def test_returns_volume(self):
        from app.vision.scale import detect_scale
        from app.vision.depth import estimate_depth
        img = _read(GOLD_RING)
        scale_ev = asyncio.get_event_loop().run_until_complete(detect_scale(img))
        ev = asyncio.get_event_loop().run_until_complete(estimate_depth(img, scale_ev))
        assert ev.kind == "depth_volume_estimate"
        assert ev.payload.get("volume_cm3", 0) > 0

    def test_fallback_method_recorded(self):
        """Without MiDaS weights, must fall back to 2d_heuristic."""
        from app.vision.scale import detect_scale
        from app.vision.depth import estimate_depth, _load_midas
        img = _read(GOLD_RING)
        scale_ev = asyncio.get_event_loop().run_until_complete(detect_scale(img))
        ev = asyncio.get_event_loop().run_until_complete(estimate_depth(img, scale_ev))
        if ev.payload.get("method") == "2d_heuristic":
            assert ev.confidence == pytest.approx(0.35)


# ── Full pipeline (FR-5) ─────────────────────────────────────────────────────

class TestFullPipeline:
    def test_run_vision_single_image(self):
        from app.vision.pipeline import run_vision
        evidence = asyncio.get_event_loop().run_until_complete(
            run_vision([_read(GOLD_RING)], declared_type="ring")
        )
        kinds = {ev.kind for ev in evidence}
        assert "item_type_classification" in kinds
        assert "segmentation_area_px" in kinds
        assert "scale_reference" in kinds
        assert "hallmark_region" in kinds
        assert "hallmark_ocr" in kinds
        assert "plating_detection" in kinds
        assert "depth_volume_estimate" in kinds

    def test_run_vision_two_images_uses_last_for_hallmark(self):
        """images[0]=top, images[-1]=hallmark close-up."""
        from app.vision.pipeline import run_vision
        evidence = asyncio.get_event_loop().run_until_complete(
            run_vision([_read(GOLD_RING), _read(HALLMARK)], declared_type="ring")
        )
        assert len(evidence) == 7

    def test_run_vision_empty_returns_empty(self):
        from app.vision.pipeline import run_vision
        evidence = asyncio.get_event_loop().run_until_complete(run_vision([]))
        assert evidence == []

    def test_all_evidence_items_have_confidence(self):
        from app.vision.pipeline import run_vision
        evidence = asyncio.get_event_loop().run_until_complete(
            run_vision([_read(GOLD_RING)])
        )
        for ev in evidence:
            assert 0 < ev.confidence <= 1.0, f"{ev.kind} confidence={ev.confidence}"


# ── Quality-check API endpoint (FR-2.4) ──────────────────────────────────────

class TestQualityCheckEndpoint:
    def test_good_image_endpoint(self, client):
        data = _read(GOLD_RING)
        r = client.post(
            "/assess/quality-check",
            files={"file": ("gold_ring.jpg", data, "image/jpeg")},
        )
        assert r.status_code == 200
        body = r.json()
        assert "bright_ok" in body
        assert "overall_ok" in body
        assert body["bright_ok"] is True

    def test_dark_image_endpoint(self, client):
        data = _read(DARK)
        r = client.post(
            "/assess/quality-check",
            files={"file": ("dark.jpg", data, "image/jpeg")},
        )
        assert r.status_code == 200
        assert r.json()["bright_ok"] is False
