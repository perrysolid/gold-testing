"""FR-7.1: Multimodal fusion engine.

Weighted evidence combination per config/decision_rules.yaml.
FR-6.3: All outputs are ranges + confidence, never point estimates.
FR-7.2: Conflict detector for WEIGHT_INCONSISTENCY.
FR-7.3: Hallmark trust boosters/caps.
"""
from __future__ import annotations

import math
from typing import Optional

from app.assess.schemas import (
    AssessmentRequest,
    AuthenticityRisk,
    EvidenceItem,
    FusionResult,
    PurityBand,
    TypeEstimate,
    WeightBand,
)
from app.fusion.weight_model import estimate_weight
from app.fusion.purity_model import estimate_purity

# Density table (g/cm³) per karat — §10.7
DENSITY: dict[int, float] = {24: 19.32, 22: 17.7, 18: 15.5, 14: 13.0}

PURITY_MAP: dict[str, tuple[int, int, int, int]] = {
    "999": (24, 24, 999, 999),
    "916": (22, 22, 916, 916),
    "875": (20, 22, 875, 916),
    "750": (18, 18, 750, 750),
    "585": (14, 14, 585, 585),
    "375": (9,  9,  375, 375),
}


def fuse(
    request: AssessmentRequest,
    vision_evidence: list[EvidenceItem],
    audio_evidence: Optional[EvidenceItem],
) -> FusionResult:
    """FR-7.1: Combine all modality evidence into a unified FusionResult."""
    all_evidence = list(vision_evidence)
    if audio_evidence:
        all_evidence.append(audio_evidence)

    # ── Pull named evidence items ─────────────────────────────────────────────
    ocr_ev = _find(all_evidence, "hallmark_ocr")
    seg_ev = _find(all_evidence, "segmentation_area_px")
    scale_ev = _find(all_evidence, "scale_reference")
    depth_ev = _find(all_evidence, "depth_volume_estimate")
    type_ev = _find(all_evidence, "item_type_classification")
    plating_ev = _find(all_evidence, "plating_detection")
    audio_ev = _find(all_evidence, "audio_tap")

    item_type = TypeEstimate(
        value=type_ev.payload.get("class", "ring") if type_ev else request.item_declared.type,
        confidence=type_ev.confidence if type_ev else 0.4,
    )

    flags: list[str] = []

    # ── Purity fusion (FR-7.3, §12.2) ────────────────────────────────────────
    purity = estimate_purity(
        ocr_ev=ocr_ev,
        audio_ev=audio_ev,
        declared_stamp=request.item_declared.declared_karat_stamp,
        flags=flags,
    )

    # ── Weight fusion (FR-6.1, §12.1) ────────────────────────────────────────
    weight = estimate_weight(
        seg_ev=seg_ev,
        scale_ev=scale_ev,
        depth_ev=depth_ev,
        item_type=item_type.value,
        purity_karat=purity.karat_low,
        declared_weight_g=request.item_declared.declared_weight_g,
        flags=flags,
    )

    # ── Scale detected flag ───────────────────────────────────────────────────
    if scale_ev and scale_ev.payload.get("type") == "aruco":
        flags.append("COIN_SCALE_DETECTED")

    # ── Risk score (§12.3) ────────────────────────────────────────────────────
    plating_risk = float(plating_ev.payload.get("plating_risk", 0.3)) if plating_ev else 0.3
    multiview_consistency = 1.0  # TODO FR-8.2: CLIP check
    fake_hallmark_risk = 0.0  # TODO FR-8.1: hallmark sanity
    weight_inconsistency = 1.0 if "WEIGHT_INCONSISTENCY" in flags else 0.0
    duplicate_risk = 0.0

    risk_score = (
        0.4 * plating_risk
        + 0.2 * (1.0 - multiview_consistency)
        + 0.2 * fake_hallmark_risk
        + 0.1 * weight_inconsistency
        + 0.1 * duplicate_risk
    )
    risk_score = min(risk_score, 1.0)
    risk_level = "LOW" if risk_score < 0.30 else ("HIGH" if risk_score >= 0.65 else "MEDIUM")
    if risk_level == "HIGH":
        flags.append("HIGH_RISK")

    return FusionResult(
        assessment_id=request.assessment_id,
        item_type=item_type,
        weight_g=weight,
        purity=purity,
        authenticity_risk=AuthenticityRisk(level=risk_level, score=round(risk_score, 3)),
        flags=flags,
        evidence=all_evidence,
    )


def _find(evidence: list[EvidenceItem], kind: str) -> Optional[EvidenceItem]:
    return next((e for e in evidence if e.kind == kind), None)
