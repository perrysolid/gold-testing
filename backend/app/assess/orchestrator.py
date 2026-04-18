"""FR-7.1: Orchestrator — runs vision + audio in parallel, then fuses.

Phase hours 5–17 will flesh out each worker. For now this is a
rule-based stub that produces a valid DecisionResult for demo flow.
"""
from __future__ import annotations

import json
import structlog

from app.assess.schemas import AssessmentRequest, FusionResult
from app.fusion.engine import fuse
from app.decision.engine import decide
from app.services.gemini import explain
from app.services.gold_price import get_gold_price
from app.db.models import Assessment, Decision, get_session
from sqlmodel import select

logger = structlog.get_logger()


async def run_pipeline(assessment_id: str, request: AssessmentRequest) -> None:
    """Entry point called by BackgroundTasks. Catches all exceptions."""
    log = logger.bind(assessment_id=assessment_id)
    try:
        log.info("pipeline.start")

        # ── Vision (FR-5) ─────────────────────────────────────────────────────
        from app.vision.classifier import classify_type
        from app.vision.segmenter import segment
        from app.vision.scale import detect_scale
        from app.vision.hallmark_detector import detect_hallmark
        from app.vision.hallmark_ocr import ocr_hallmark
        from app.vision.plating_detector import detect_plating
        from app.vision.depth import estimate_depth
        from app.vision.quality import check_quality

        # ── Audio (FR-3) ──────────────────────────────────────────────────────
        from app.audio.tap_features import extract_features

        # ── Fraud (FR-8) ──────────────────────────────────────────────────────
        from app.fraud.image_dedup import check_dedup
        from app.fraud.multiview_consistency import check_consistency
        from app.fraud.hallmark_sanity import check_hallmark_sanity

        # Stub: load artifact bytes from object store
        # TODO: resolve object_keys from request.artifacts via services/object_store.py
        image_bytes_list: list[bytes] = []
        audio_bytes: bytes | None = None

        vision_evidence = []
        audio_evidence = None

        # Run classifiers (stubs return safe defaults when model not loaded)
        if image_bytes_list:
            item_type_ev = await classify_type(image_bytes_list[0])
            seg_ev = await segment(image_bytes_list[0], item_type_ev)
            scale_ev = await detect_scale(image_bytes_list[0])
            hallmark_ev = await detect_hallmark(image_bytes_list[-1] if len(image_bytes_list) >= 3 else image_bytes_list[0])
            ocr_ev = await ocr_hallmark(image_bytes_list[-1] if len(image_bytes_list) >= 3 else image_bytes_list[0], hallmark_ev)
            plating_ev = await detect_plating(image_bytes_list[0], seg_ev)
            depth_ev = await estimate_depth(image_bytes_list[0], scale_ev)
            vision_evidence = [e for e in [seg_ev, scale_ev, hallmark_ev, ocr_ev, plating_ev, depth_ev] if e]

        if audio_bytes:
            audio_evidence = await extract_features(audio_bytes)

        # ── Fusion (FR-7.1) ───────────────────────────────────────────────────
        fusion: FusionResult = fuse(
            request=request,
            vision_evidence=vision_evidence,
            audio_evidence=audio_evidence,
        )

        # ── Decision (FR-7.4) ─────────────────────────────────────────────────
        gold_price = await get_gold_price()
        decision_result = decide(fusion, gold_price)

        # ── Explanation (FR-9.2) ──────────────────────────────────────────────
        why_bullets = await explain(fusion, decision_result)
        decision_result.why = why_bullets

        # ── Persist ───────────────────────────────────────────────────────────
        async with get_session() as session:  # type: ignore[attr-defined]
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
                    explanation_md="\n".join(decision_result.why),
                    rationale_json=json.dumps(fusion.model_dump()),
                )
                session.add(db_decision)
                await session.commit()

        log.info("pipeline.done", decision=decision_result.decision)

    except Exception as exc:
        log.exception("pipeline.error", error=str(exc))
        async with get_session() as session:  # type: ignore[attr-defined]
            result = await session.exec(select(Assessment).where(Assessment.id == assessment_id))
            assessment = result.first()
            if assessment:
                assessment.status = "error"
                session.add(assessment)
                await session.commit()
