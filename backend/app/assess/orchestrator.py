"""FR-7.1: Orchestrator — loads artifacts, runs vision + audio, fuses, decides.

Artifacts are read from the local object store (uploaded via /assess/upload).
Each vision stage falls back gracefully when models aren't loaded (NFR-9).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import structlog

from app.assess.schemas import AssessmentRequest, FusionResult
from app.config import get_settings
from app.db.models import Assessment, Decision, session_ctx
from app.decision.engine import decide
from app.fusion.engine import fuse
from app.services.gemini import explain
from app.services.gold_price import get_gold_price
from sqlmodel import select

logger = structlog.get_logger()
settings = get_settings()


def _load_artifact(assessment_id: str, kind: str) -> Optional[bytes]:
    path = Path(settings.local_storage_path) / assessment_id / kind
    if path.exists():
        return path.read_bytes()
    return None


async def run_pipeline(assessment_id: str, request: AssessmentRequest) -> None:
    """Entry point called by BackgroundTasks. Catches all exceptions."""
    log = logger.bind(assessment_id=assessment_id)
    try:
        log.info("pipeline.start", item_type=request.item_declared.type)

        # ── Load uploaded artifacts ───────────────────────────────────────────
        image_bytes_list: list[bytes] = []
        for kind in ("image_top", "image_side", "image_hallmark"):
            data = _load_artifact(assessment_id, kind)
            if data:
                image_bytes_list.append(data)

        audio_bytes = _load_artifact(assessment_id, "audio")

        # ── Vision pipeline (FR-5) ────────────────────────────────────────────
        vision_evidence = []
        if image_bytes_list:
            from app.vision.pipeline import run_vision
            vision_evidence = await run_vision(
                image_bytes_list,
                declared_type=request.item_declared.type,
            )
            log.info("pipeline.vision_done", evidence_count=len(vision_evidence))
        else:
            log.warning("pipeline.no_images", fallback="fusing from self-report only")

        # ── Audio pipeline (FR-3) ─────────────────────────────────────────────
        audio_evidence = None
        if audio_bytes:
            from app.audio.tap_features import extract_features
            audio_evidence = await extract_features(audio_bytes)
            log.info("pipeline.audio_done", class_=audio_evidence.payload.get("class") if audio_evidence else None)

        # ── FR-8.2: Multi-view consistency (async, before sync fuse()) ────────
        multiview_consistency = 1.0
        if len(image_bytes_list) > 1:
            from app.fraud.multiview_consistency import check_consistency
            multiview_consistency = await check_consistency(image_bytes_list)
            log.debug("pipeline.consistency", score=multiview_consistency)

        # ── Fusion (FR-7.1) ───────────────────────────────────────────────────
        fusion: FusionResult = fuse(
            request=request,
            vision_evidence=vision_evidence,
            audio_evidence=audio_evidence,
            image_bytes_list=image_bytes_list or None,
            multiview_consistency=multiview_consistency,
        )

        # ── Decision (FR-7.4) ─────────────────────────────────────────────────
        gold_price = await get_gold_price()
        decision_result = decide(fusion, gold_price)

        # ── Explanation (FR-9.2) ──────────────────────────────────────────────
        decision_result.why = await explain(fusion, decision_result)

        # ── Build rationale JSON for Result screen ────────────────────────────
        rationale = {
            "headline": decision_result.headline,
            "next_steps_md": decision_result.next_steps_md,
            "weight_g": fusion.weight_g.model_dump(),
            "purity": fusion.purity.model_dump(),
            "authenticity_risk": fusion.authenticity_risk.model_dump(),
            "flags": fusion.flags,
            "evidence": [e.model_dump() for e in fusion.evidence],
        }

        # ── Persist ───────────────────────────────────────────────────────────
        async with session_ctx() as session:
            result = await session.exec(select(Assessment).where(Assessment.id == assessment_id))
            assessment = result.first()
            if assessment:
                assessment.status = "done"
                assessment.decision = decision_result.decision
                session.add(assessment)

            db_decision = Decision(
                assessment_id=assessment_id,
                decision=decision_result.decision,
                max_loan_inr=decision_result.max_loan_inr,
                explanation_md="\n".join(f"- {b}" for b in decision_result.why),
                rationale_json=json.dumps(rationale),
            )
            session.add(db_decision)
            await session.commit()

        log.info("pipeline.done", decision=decision_result.decision, loan=decision_result.max_loan_inr)

    except Exception as exc:
        log.exception("pipeline.error", error=str(exc))
        async with session_ctx() as session:
            result = await session.exec(select(Assessment).where(Assessment.id == assessment_id))
            assessment = result.first()
            if assessment:
                assessment.status = "error"
                session.add(assessment)
                await session.commit()
