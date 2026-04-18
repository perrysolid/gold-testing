"""FR-7.1/FR-7.2/FR-7.3: Fusion engine table-driven tests (§16)."""
from __future__ import annotations

import pytest

from app.assess.schemas import AssessmentRequest, ArtifactRef, ConsentRecord, EvidenceItem, ItemDeclared
from app.fusion.engine import fuse
from app.fusion.purity_model import estimate_purity
from app.fusion.weight_model import estimate_weight
from datetime import datetime, timezone


def _req(item_type: str = "ring", weight: float | None = None, stamp: str | None = None) -> AssessmentRequest:
    return AssessmentRequest(
        assessment_id="t1",
        item_declared=ItemDeclared(
            type=item_type,
            declared_weight_g=weight,
            declared_karat_stamp=stamp,
        ),
        artifacts=[ArtifactRef(kind="image_top", object_key="k1", sha256="abc")],
        consent=ConsentRecord(version="v1", signed_at=datetime.now(timezone.utc)),
    )


def _ocr_ev(purity_mark: str | None, bis: bool = True, huid: str | None = "AB12CD", conf: float = 0.85) -> EvidenceItem:
    return EvidenceItem(
        id="ev_ocr",
        kind="hallmark_ocr",
        payload={
            "purity_mark": purity_mark,
            "bis_logo": bis,
            "huid": huid,
            "huid_valid": huid is not None,
            "purity_valid": purity_mark is not None,
        },
        confidence=conf,
    )


def test_valid_hallmark_boosts_purity_conf() -> None:
    flags: list[str] = []
    band = estimate_purity(ocr_ev=_ocr_ev("916"), audio_ev=None, declared_stamp=None, flags=flags)
    assert band.confidence >= 0.95
    assert "HALLMARK_VALID_BIS" in flags


def test_missing_hallmark_claimed_22k_caps_at_55() -> None:
    flags: list[str] = []
    band = estimate_purity(ocr_ev=None, audio_ev=None, declared_stamp="22K", flags=flags)
    assert band.confidence <= 0.55
    assert "HALLMARK_MISSING_CAPPED" in flags


def test_weight_inconsistency_flagged() -> None:
    seg_ev = EvidenceItem(id="e1", kind="segmentation_area_px",
                          payload={"mask_area_px": 50_000, "mask_bbox": [0, 0, 100, 100]}, confidence=0.8)
    scale_ev = EvidenceItem(id="e2", kind="scale_reference",
                            payload={"pixels_per_mm": 10.0}, confidence=0.9)
    depth_ev = EvidenceItem(id="e3", kind="depth_volume_estimate",
                            payload={"volume_cm3": 0.3}, confidence=0.6)
    flags: list[str] = []
    weight = estimate_weight(seg_ev, scale_ev, depth_ev, "ring", 22, declared_weight_g=200.0, flags=flags)
    assert "WEIGHT_INCONSISTENCY" in flags


def test_fuse_returns_valid_fusion_result() -> None:
    req = _req("chain", weight=10.0, stamp="916")
    result = fuse(req, vision_evidence=[], audio_evidence=None)
    assert result.weight_g.low < result.weight_g.high
    assert 0 <= result.weight_g.confidence <= 1
    assert 0 <= result.purity.confidence <= 1
    assert result.authenticity_risk.level in {"LOW", "MEDIUM", "HIGH"}
