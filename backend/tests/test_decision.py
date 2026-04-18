"""FR-7.4: Table-driven decision engine tests (§16)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.assess.schemas import (
    AuthenticityRisk,
    EvidenceItem,
    FusionResult,
    GoldPriceSnapshot,
    PurityBand,
    TypeEstimate,
    WeightBand,
)
from app.decision.engine import decide

GOLD = GoldPriceSnapshot(inr_per_g_22k=6900.0, fetched_at=datetime.now(timezone.utc))


def _make_fusion(
    purity_conf: float = 0.85,
    weight_conf: float = 0.80,
    risk_score: float = 0.10,
    flags: list[str] | None = None,
    purity_karat: int = 22,
    fineness: int = 916,
    weight_low: float = 8.0,
    weight_high: float = 12.0,
) -> FusionResult:
    return FusionResult(
        assessment_id="test-123",
        item_type=TypeEstimate(value="ring", confidence=0.9),
        weight_g=WeightBand(low=weight_low, high=weight_high, confidence=weight_conf, method="test"),
        purity=PurityBand(
            karat_low=purity_karat, karat_high=purity_karat,
            fineness_low=fineness, fineness_high=fineness,
            confidence=purity_conf, primary_signal="hallmark_ocr",
        ),
        authenticity_risk=AuthenticityRisk(level="LOW" if risk_score < 0.3 else "HIGH", score=risk_score),
        flags=flags or [],
        evidence=[],
    )


@pytest.mark.parametrize("case,fusion_kwargs,expected_decision", [
    ("all_good_pre_approve", {}, "PRE_APPROVE"),
    ("low_purity_conf", {"purity_conf": 0.5}, "NEEDS_VERIFICATION"),
    ("low_weight_conf", {"weight_conf": 0.5}, "NEEDS_VERIFICATION"),
    ("high_risk", {"risk_score": 0.8}, "REJECT"),
    ("fatal_flag", {"flags": ["FAKE_HALLMARK_DETECTED"], "risk_score": 0.1}, "REJECT"),
    ("plated_flag", {"flags": ["PLATED_HIGH_CONFIDENCE"]}, "REJECT"),
    ("borderline_approve", {"purity_conf": 0.76, "weight_conf": 0.71, "risk_score": 0.29}, "PRE_APPROVE"),
    ("borderline_verify", {"purity_conf": 0.74, "weight_conf": 0.71}, "NEEDS_VERIFICATION"),
])
def test_decision(case: str, fusion_kwargs: dict, expected_decision: str) -> None:
    fusion = _make_fusion(**fusion_kwargs)
    result = decide(fusion, GOLD)
    assert result.decision == expected_decision, f"{case}: got {result.decision}"


def test_loan_calculation() -> None:
    fusion = _make_fusion(weight_low=8.0, fineness=916)
    result = decide(fusion, GOLD)
    # equiv_22k = 8.0 * (916/916) = 8.0; gross = 8.0 * 6900 = 55200; ltv=0.85 → 46920
    assert result.max_loan_inr == 46920
    assert result.ltv_applied == 0.85


def test_no_loan_on_reject() -> None:
    fusion = _make_fusion(risk_score=0.9)
    result = decide(fusion, GOLD)
    assert result.decision == "REJECT"
    assert result.max_loan_inr is None


def test_health(client: "TestClient") -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
