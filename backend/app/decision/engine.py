"""FR-7.4: Decision engine — reads rules.yaml, applies thresholds, computes loan.

US-C1: Rules hot-reloaded on SIGHUP.
FR-7.5: Loan calculation per RBI LTV tiers.
"""
from __future__ import annotations

import math
import os
import signal
from pathlib import Path
from typing import Any

import yaml
import structlog

from app.assess.schemas import DecisionResult, FusionResult, GoldPriceSnapshot

logger = structlog.get_logger()

_rules: dict[str, Any] = {}
_RULES_PATH = Path(__file__).parent / "rules.yaml"


def _load_rules() -> dict[str, Any]:
    global _rules
    with open(_RULES_PATH) as f:
        _rules = yaml.safe_load(f)
    logger.info("decision.rules_loaded", version=_rules.get("version"))
    return _rules


def get_rules() -> dict[str, Any]:
    if not _rules:
        _load_rules()
    return _rules


# Hot-reload on SIGHUP (US-C1)
def _sighup_handler(signum: int, frame: object) -> None:
    _load_rules()

signal.signal(signal.SIGHUP, _sighup_handler)


def decide(fusion: FusionResult, gold_price: GoldPriceSnapshot) -> DecisionResult:
    """FR-7.4: Apply YAML rules → decision + loan amount."""
    rules = get_rules()
    thresh = rules["thresholds"]

    purity_conf = fusion.purity.confidence
    weight_conf = fusion.weight_g.confidence
    risk_score = fusion.authenticity_risk.score
    flags = set(fusion.flags)

    # Fatal flag check (immediate REJECT)
    fatal = set(thresh["reject"]["fatal_flags"])
    if flags & fatal:
        decision = "REJECT"
    elif risk_score >= thresh["reject"]["max_risk_score"]:
        decision = "REJECT"
    elif (
        purity_conf >= thresh["pre_approve"]["min_purity_confidence"]
        and weight_conf >= thresh["pre_approve"]["min_weight_confidence"]
        and risk_score <= thresh["pre_approve"]["max_risk_score"]
    ):
        decision = "PRE_APPROVE"
    else:
        decision = "NEEDS_VERIFICATION"

    # FR-7.5: Loan calculation
    max_loan_inr: int | None = None
    ltv_applied: float | None = None
    if decision != "REJECT":
        ltv_cfg = rules.get("ltv", {})
        weight_low = fusion.weight_g.low
        fineness_low = fusion.purity.fineness_low
        price_22k = gold_price.inr_per_g_22k
        equiv_22k = weight_low * (fineness_low / 916.0)
        gross = equiv_22k * price_22k
        ltv = (
            ltv_cfg.get("small_ticket_rate", 0.85)
            if gross <= ltv_cfg.get("small_ticket_max_inr", 250_000)
            else ltv_cfg.get("default_rate", 0.75)
        )
        max_loan_inr = math.floor(gross * ltv)
        ltv_applied = ltv

    karat_str = f"{fusion.purity.karat_low}K–{fusion.purity.karat_high}K"
    weight_str = f"{fusion.weight_g.low}–{fusion.weight_g.high} g"
    headline = f"Estimated {weight_str}, {karat_str}, {fusion.authenticity_risk.level.lower()} risk"

    next_steps = {
        "PRE_APPROVE": "Visit a branch within 14 days to complete physical verification and disbursal.",
        "NEEDS_VERIFICATION": "Bring your jewellery to the nearest branch for expert verification.",
        "REJECT": "We cannot process a loan for this item. Please visit a branch for assistance.",
    }

    return DecisionResult(
        assessment_id=fusion.assessment_id,
        decision=decision,
        headline=headline,
        max_loan_inr=max_loan_inr,
        ltv_applied=ltv_applied,
        gold_price_used=gold_price,
        why=[],  # filled by Gemini in orchestrator
        next_steps_md=next_steps[decision],
        evidence=fusion.evidence,
    )
