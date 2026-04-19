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
            from app.vision.classifier import classify_type
            from app.vision.segmenter import segment
            from app.vision.scale import detect_scale
            from app.vision.hallmark_detector import detect_hallmark
            from app.vision.hallmark_ocr import ocr_hallmark
            from app.vision.plating_detector import detect_plating
            from app.vision.depth import estimate_depth

            primary = image_bytes_list[0]
            hallmark_img = image_bytes_list[-1]  # last image = closest to hallmark shot

            type_ev = await classify_type(primary)
            seg_ev = await segment(primary, type_ev)
            scale_ev = await detect_scale(primary)
            hallmark_ev = await detect_hallmark(hallmark_img)
            ocr_ev = await ocr_hallmark(hallmark_img, hallmark_ev)
            plating_ev = await detect_plating(primary, seg_ev)
            depth_ev = await estimate_depth(primary, scale_ev)

            vision_evidence = [type_ev, seg_ev, scale_ev, hallmark_ev, ocr_ev, plating_ev, depth_ev]
            log.info("pipeline.vision_done", evidence_count=len(vision_evidence))
        else:
            log.warning("pipeline.no_images", fallback="fusing from self-report only")

        # ── Audio pipeline (FR-3) ─────────────────────────────────────────────
        audio_evidence = None
        if audio_bytes:
            from app.audio.tap_features import extract_features
            audio_evidence = await extract_features(audio_bytes)
            log.info("pipeline.audio_done", class_=audio_evidence.payload.get("class") if audio_evidence else None)

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
