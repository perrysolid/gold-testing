"""Canonical data contracts per §6 of IMPLEMENTATION_PLAN.

FR-6.3: All weight/purity outputs are ranges + confidence, never point estimates.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Request types (§6.1) ──────────────────────────────────────────────────────

class ItemDeclared(BaseModel):
    type: str  # ring|chain|bangle|earring|pendant|coin|bar
    declared_weight_g: Optional[float] = None
    declared_karat_stamp: Optional[str] = None
    declared_total_value_inr: Optional[float] = None
    notes: Optional[str] = None


class ArtifactRef(BaseModel):
    kind: str  # image_top|image_side|image_hallmark|audio
    object_key: str
    sha256: str
    optional: bool = False


class ConsentRecord(BaseModel):
    version: str = "v1"
    signed_at: datetime


class AssessmentRequest(BaseModel):
    assessment_id: str
    item_declared: ItemDeclared
    artifacts: list[ArtifactRef]
    consent: ConsentRecord


# ── Internal fusion result (§6.2) ─────────────────────────────────────────────

class TypeEstimate(BaseModel):
    value: str
    confidence: float = Field(ge=0.0, le=1.0)


class WeightBand(BaseModel):
    """FR-6.3: Always a range, never a point estimate."""
    low: float
    high: float
    confidence: float = Field(ge=0.0, le=1.0)
    method: str = "rule_based"


class PurityBand(BaseModel):
    """FR-6.3: Always a range, never a point estimate."""
    karat_low: int
    karat_high: int
    fineness_low: int
    fineness_high: int
    confidence: float = Field(ge=0.0, le=1.0)
    primary_signal: str = "self_report"


class AuthenticityRisk(BaseModel):
    level: str  # LOW | MEDIUM | HIGH
    score: float = Field(ge=0.0, le=1.0)


class EvidenceItem(BaseModel):
    id: str
    kind: str
    payload: dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)


class FusionResult(BaseModel):
    assessment_id: str
    item_type: TypeEstimate
    weight_g: WeightBand
    purity: PurityBand
    authenticity_risk: AuthenticityRisk
    flags: list[str] = []
    evidence: list[EvidenceItem] = []


# ── Decision result (§6.3) ────────────────────────────────────────────────────

class GoldPriceSnapshot(BaseModel):
    inr_per_g_22k: float
    fetched_at: datetime


class DecisionResult(BaseModel):
    assessment_id: str
    decision: str  # PRE_APPROVE | NEEDS_VERIFICATION | REJECT
    headline: str
    max_loan_inr: Optional[int] = None
    ltv_applied: Optional[float] = None
    gold_price_used: Optional[GoldPriceSnapshot] = None
    why: list[str] = []
    next_steps_md: str = ""
    evidence: list[EvidenceItem] = []


# ── Upload helpers ────────────────────────────────────────────────────────────

class AssessmentStartResponse(BaseModel):
    assessment_id: str
    upload_urls: dict[str, str]
