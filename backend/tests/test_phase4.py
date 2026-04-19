"""Phase 4: Fusion engine, fraud checks, decision, orchestrator end-to-end."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.assess.schemas import (
    ArtifactRef, AssessmentRequest, ConsentRecord,
    EvidenceItem, ItemDeclared,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _req(item_type="ring", weight=None, stamp=None, aid="test-assess-01"):
    return AssessmentRequest(
        assessment_id=aid,
        item_declared=ItemDeclared(
            type=item_type,
            declared_weight_g=weight,
            declared_karat_stamp=stamp,
        ),
        artifacts=[ArtifactRef(kind="image_top", object_key="k1", sha256="abc")],
        consent=ConsentRecord(version="v1", signed_at=datetime.now(timezone.utc)),
    )


def _ocr(purity="916", bis=True, huid="AB12CD", conf=0.85):
    return EvidenceItem(
        id="ev_ocr", kind="hallmark_ocr",
        payload={"purity_mark": purity, "bis_logo": bis, "huid": huid,
                 "huid_valid": huid is not None, "purity_valid": purity is not None},
        confidence=conf,
    )


# ── Hallmark sanity (FR-8.1) ─────────────────────────────────────────────────

class TestHallmarkSanity:
    def test_valid_huid_no_risk(self):
        from app.fraud.hallmark_sanity import check_hallmark_sanity
        risk, flags = check_hallmark_sanity(_ocr("916", bis=True, huid="AB12CD"))
        assert risk == pytest.approx(0.0)
        assert "FAKE_HALLMARK_DETECTED" not in flags

    def test_invalid_huid_raises_risk(self):
        from app.fraud.hallmark_sanity import check_hallmark_sanity
        ev = EvidenceItem(id="e", kind="hallmark_ocr",
                          payload={"huid": "!!BAD", "bis_logo": True, "purity_mark": "916",
                                   "huid_valid": False, "purity_valid": True},
                          confidence=0.8)
        risk, flags = check_hallmark_sanity(ev)
        assert risk > 0
        assert "HUID_FORMAT_INVALID" in flags

    def test_bis_no_purity_raises_risk(self):
        from app.fraud.hallmark_sanity import check_hallmark_sanity
        ev = EvidenceItem(id="e", kind="hallmark_ocr",
                          payload={"huid": None, "bis_logo": True, "purity_mark": None,
                                   "huid_valid": False, "purity_valid": False},
                          confidence=0.5)
        risk, flags = check_hallmark_sanity(ev)
        assert "BIS_LOGO_NO_PURITY" in flags

    def test_no_ocr_returns_zero(self):
        from app.fraud.hallmark_sanity import check_hallmark_sanity
        risk, flags = check_hallmark_sanity(None)
        assert risk == 0.0 and flags == []


# ── Image dedup (FR-8.3) ─────────────────────────────────────────────────────

class TestImageDedup:
    def test_first_submission_not_duplicate(self):
        from app.fraud.image_dedup import check_dedup, _seen_hashes
        _seen_hashes.clear()
        risk, flags = check_dedup(b"unique_image_bytes_xyz_" + b"x" * 100)
        assert risk == 0.0
        assert "DUPLICATE_SUBMISSION" not in flags

    def test_second_identical_submission_flagged(self):
        from app.fraud.image_dedup import check_dedup, _seen_hashes
        _seen_hashes.clear()
        data = b"duplicate_test_data_" + b"y" * 100
        check_dedup(data)  # first
        risk, flags = check_dedup(data)  # second
        assert risk == 1.0
        assert "DUPLICATE_SUBMISSION" in flags


# ── CLIP consistency (FR-8.2) ────────────────────────────────────────────────

class TestMultiviewConsistency:
    def test_single_image_returns_one(self):
        from app.fraud.multiview_consistency import check_consistency
        score = asyncio.get_event_loop().run_until_complete(
            check_consistency([(Path(FIXTURES / "gold_ring.jpg")).read_bytes()])
        )
        assert score == pytest.approx(1.0)

    def test_no_clip_falls_back_to_09(self):
        """Without clip package, returns 0.9 (assume consistent)."""
        from app.fraud.multiview_consistency import check_consistency, _load_clip
        model, _ = _load_clip()
        if model is None:
            score = asyncio.get_event_loop().run_until_complete(
                check_consistency([b"img1", b"img2"])
            )
            assert score == pytest.approx(0.9)


# ── Full fusion (FR-7.1) ─────────────────────────────────────────────────────

class TestFusion:
    def test_good_item_low_risk(self):
        from app.fusion.engine import fuse
        req = _req("ring", weight=8.0, stamp="916")
        result = fuse(req, vision_evidence=[_ocr()], audio_evidence=None)
        assert result.authenticity_risk.score < 0.60
        assert result.weight_g.low < result.weight_g.high
        assert result.purity.confidence >= 0.75  # BIS + HUID boost

    def test_fake_hallmark_raises_risk(self):
        from app.fusion.engine import fuse
        bad_ocr = EvidenceItem(
            id="e", kind="hallmark_ocr",
            payload={"huid": "!!!BAD", "bis_logo": True, "purity_mark": None,
                     "huid_valid": False, "purity_valid": False},
            confidence=0.3,
        )
        req = _req()
        result = fuse(req, vision_evidence=[bad_ocr], audio_evidence=None)
        assert any(f in result.flags for f in ("FAKE_HALLMARK_DETECTED", "BIS_LOGO_NO_PURITY", "HUID_FORMAT_INVALID", "HALLMARK_LOW_CONF"))

    def test_flags_deduplicated(self):
        from app.fusion.engine import fuse
        req = _req()
        result = fuse(req, vision_evidence=[], audio_evidence=None)
        assert len(result.flags) == len(set(result.flags))

    def test_weight_band_uses_lightgbm_when_model_exists(self):
        """With models/weight_lgbm.pkl trained, method should be 'lightgbm'."""
        import os
        from app.fusion.weight_model import estimate_weight, _load_lgbm, _lgbm
        import app.fusion.weight_model as wm
        wm._lgbm = None  # reset cache so it reloads
        seg_ev = EvidenceItem(id="e1", kind="segmentation_area_px",
                              payload={"mask_area_px": 50_000}, confidence=0.8)
        scale_ev = EvidenceItem(id="e2", kind="scale_reference",
                                payload={"pixels_per_mm": 10.0}, confidence=0.9)
        depth_ev = EvidenceItem(id="e3", kind="depth_volume_estimate",
                                payload={"volume_cm3": 0.5, "thickness_mm": 3.0}, confidence=0.6)
        flags: list[str] = []
        band = estimate_weight(seg_ev, scale_ev, depth_ev, "ring", 22, None, flags)
        if os.path.exists("models/weight_lgbm.pkl"):
            assert band.method == "lightgbm"
            assert band.confidence > 0.5


# ── Decision engine (FR-7.4) ─────────────────────────────────────────────────

class TestDecision:
    def _gold_price(self):
        from app.assess.schemas import GoldPriceSnapshot
        from datetime import datetime, timezone
        return GoldPriceSnapshot(inr_per_g_22k=6900.0, fetched_at=datetime.now(timezone.utc))

    def _make_fusion(self, purity_conf=0.80, weight_conf=0.75, risk_score=0.20, flags=None):
        from app.assess.schemas import (
            FusionResult, WeightBand, PurityBand, AuthenticityRisk, TypeEstimate
        )
        return FusionResult(
            assessment_id="t1",
            item_type=TypeEstimate(value="ring", confidence=0.9),
            weight_g=WeightBand(low=8.0, high=12.0, confidence=weight_conf, method="test"),
            purity=PurityBand(karat_low=22, karat_high=22, fineness_low=916,
                              fineness_high=916, confidence=purity_conf, primary_signal="ocr"),
            authenticity_risk=AuthenticityRisk(level="LOW", score=risk_score),
            flags=flags or [],
            evidence=[],
        )

    def test_pre_approve_loan_calc(self):
        from app.decision.engine import decide
        fusion = self._make_fusion()
        result = decide(fusion, self._gold_price())
        assert result.decision == "PRE_APPROVE"
        assert result.max_loan_inr is not None
        # weight_low=8, fineness=916, price=6900: equiv_22k=8*1, gross=55200, LTV=85%
        assert result.max_loan_inr == pytest.approx(8 * 6900 * 0.85, abs=500)

    def test_needs_verification_when_low_purity_conf(self):
        from app.decision.engine import decide
        fusion = self._make_fusion(purity_conf=0.50)
        result = decide(fusion, self._gold_price())
        assert result.decision == "NEEDS_VERIFICATION"

    def test_reject_on_fatal_flag(self):
        from app.decision.engine import decide
        fusion = self._make_fusion(flags=["FAKE_HALLMARK_DETECTED"])
        result = decide(fusion, self._gold_price())
        assert result.decision == "REJECT"
        assert result.max_loan_inr is None

    def test_small_ticket_85pct_ltv(self):
        from app.decision.engine import decide
        fusion = self._make_fusion()
        result = decide(fusion, self._gold_price())
        assert result.ltv_applied == pytest.approx(0.85)

    def test_large_ticket_75pct_ltv(self):
        from app.assess.schemas import WeightBand, PurityBand, AuthenticityRisk, TypeEstimate, FusionResult
        from app.decision.engine import decide
        # weight=50g at 6900/g = 345k gross → above 250k threshold
        fusion = FusionResult(
            assessment_id="t1",
            item_type=TypeEstimate(value="chain", confidence=0.9),
            weight_g=WeightBand(low=50.0, high=60.0, confidence=0.80, method="test"),
            purity=PurityBand(karat_low=22, karat_high=22, fineness_low=916,
                              fineness_high=916, confidence=0.85, primary_signal="ocr"),
            authenticity_risk=AuthenticityRisk(level="LOW", score=0.10),
            flags=[],
            evidence=[],
        )
        result = decide(fusion, self._gold_price())
        assert result.ltv_applied == pytest.approx(0.75)


# ── Gemini explain template fallback (FR-9.2) ─────────────────────────────────

class TestExplainTemplate:
    def test_template_returns_bullets(self):
        from app.services.gemini import _template_explanation
        from app.assess.schemas import (
            FusionResult, WeightBand, PurityBand, AuthenticityRisk, TypeEstimate, DecisionResult, GoldPriceSnapshot
        )
        fusion = FusionResult(
            assessment_id="t1",
            item_type=TypeEstimate(value="ring", confidence=0.9),
            weight_g=WeightBand(low=8.0, high=12.0, confidence=0.75, method="test"),
            purity=PurityBand(karat_low=22, karat_high=22, fineness_low=916,
                              fineness_high=916, confidence=0.80, primary_signal="ocr"),
            authenticity_risk=AuthenticityRisk(level="LOW", score=0.15),
            flags=[],
            evidence=[],
        )
        dr = DecisionResult(
            assessment_id="t1", decision="PRE_APPROVE", headline="Test",
            max_loan_inr=46920, ltv_applied=0.85,
            gold_price_used=GoldPriceSnapshot(inr_per_g_22k=6900.0,
                                               fetched_at=datetime.now(timezone.utc)),
            why=[], next_steps_md="Visit branch.", evidence=[],
        )
        bullets = _template_explanation(fusion, dr)
        assert isinstance(bullets, list)
        assert len(bullets) >= 3
        assert any("branch" in b.lower() for b in bullets)


# ── Gold price mock (FR-11.1) ─────────────────────────────────────────────────

class TestGoldPrice:
    def test_mock_returns_snapshot(self):
        from app.services.gold_price import get_gold_price
        price = asyncio.get_event_loop().run_until_complete(get_gold_price())
        assert price.inr_per_g_22k > 0
        assert price.fetched_at is not None
