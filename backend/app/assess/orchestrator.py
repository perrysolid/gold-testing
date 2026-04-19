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
from app.vision.classifier import NON_JEWELLERY_THRESHOLD
from sqlmodel import select

logger = structlog.get_logger()
settings = get_settings()


def _load_artifact(assessment_id: str, kind: str) -> Optional[bytes]:
    path = Path(settings.local_storage_path) / assessment_id / kind
    if path.exists():
        return path.read_bytes()
    return None


async def _mark_error(assessment_id: str, reason: str = "") -> None:
    """Set assessment status to error — called from multiple places."""
    try:
        async with session_ctx() as session:
            result = await session.exec(select(Assessment).where(Assessment.id == assessment_id))
            assessment = result.first()
            if assessment:
                assessment.status = "error"
                if reason:
                    assessment.item_type = assessment.item_type  # keep existing
                session.add(assessment)
                await session.commit()
    except Exception as e:
        logger.error("pipeline.status_update_failed", error=str(e))


async def run_pipeline(assessment_id: str, request: AssessmentRequest) -> None:
    """Entry point called by BackgroundTasks. Catches all exceptions."""
    import asyncio
    log = logger.bind(assessment_id=assessment_id)
    try:
        log.info("pipeline.start", item_type=request.item_declared.type)

        async def _execute() -> None:
            # ── Load uploaded artifacts ───────────────────────────────────────
            image_bytes_list: list[bytes] = []
            for kind in ("image_top", "image_side", "image_hallmark"):
                data = _load_artifact(assessment_id, kind)
                if data:
                    image_bytes_list.append(data)

            audio_bytes = _load_artifact(assessment_id, "audio")

            if not image_bytes_list:
                log.warning("pipeline.no_images", fallback="fusing from self-report only")

            # ── Vision pipeline (FR-5) ─────────────────────────────────────────
            vision_evidence = []
            if image_bytes_list:
                from app.vision.pipeline import run_vision
                vision_evidence = await run_vision(
                    image_bytes_list,
                    declared_type=request.item_declared.type,
                )
                log.info("pipeline.vision_done", evidence_count=len(vision_evidence))

                # ── Non-jewellery gate (FR-5.1) ────────────────────────────────
                # Check first evidence item for non_jewellery classification.
                type_ev = next((e for e in vision_evidence if e.kind == "item_type_classification"), None)
                if (
                    type_ev
                    and type_ev.payload.get("class") == "non_jewellery"
                    and type_ev.confidence >= NON_JEWELLERY_THRESHOLD
                ):
                    log.warning(
                        "pipeline.rejected_non_jewellery",
                        confidence=type_ev.confidence,
                        source=type_ev.payload.get("source"),
                    )
                    await _mark_error(assessment_id)
                    # Persist a rejection decision so Result screen can show clear message
                    async with session_ctx() as session:
                        result = await session.exec(
                            select(Assessment).where(Assessment.id == assessment_id)
                        )
                        assessment = result.first()
                        if assessment:
                            assessment.status = "done"
                            assessment.decision = "REJECT"
                            session.add(assessment)
                        db_decision = Decision(
                            assessment_id=assessment_id,
                            decision="REJECT",
                            max_loan_inr=None,
                            explanation_md=(
                                "- Image does not appear to show gold jewellery.\n"
                                "- Please upload a clear photo of the jewellery item.\n"
                                "- Visit a branch if you need assistance."
                            ),
                            rationale_json=json.dumps({
                                "headline": "Image rejected — no jewellery detected",
                                "next_steps_md": "Please retake the photo showing your gold item clearly.",
                                "weight_g": {"low": 0, "high": 0, "confidence": 0, "method": "none"},
                                "purity": {
                                    "karat_low": 0, "karat_high": 0,
                                    "fineness_low": 0, "fineness_high": 0,
                                    "confidence": 0, "primary_signal": "none",
                                },
                                "authenticity_risk": {"level": "HIGH", "score": 1.0},
                                "flags": ["NON_JEWELLERY_DETECTED"],
                                "evidence": [],
                            }),
                        )
                        session.add(db_decision)
                        await session.commit()
                    return

            # ── Audio pipeline (FR-3) ──────────────────────────────────────────
            audio_evidence = None
            if audio_bytes:
                try:
                    from app.audio.tap_features import extract_features
                    audio_evidence = await extract_features(audio_bytes)
                    log.info(
                        "pipeline.audio_done",
                        class_=audio_evidence.payload.get("class") if audio_evidence else None,
                    )
                except Exception as e:
                    log.warning("pipeline.audio_failed", error=str(e))

            # ── FR-8.2: Multi-view consistency (async, before sync fuse()) ─────
            multiview_consistency = 1.0
            if len(image_bytes_list) > 1:
                try:
                    from app.fraud.multiview_consistency import check_consistency
                    multiview_consistency = await check_consistency(image_bytes_list)
                    log.debug("pipeline.consistency", score=multiview_consistency)
                except Exception as e:
                    log.warning("pipeline.consistency_failed", error=str(e))

            # ── Fusion (FR-7.1) ────────────────────────────────────────────────
            fusion: FusionResult = fuse(
                request=request,
                vision_evidence=vision_evidence,
                audio_evidence=audio_evidence,
                image_bytes_list=image_bytes_list or None,
                multiview_consistency=multiview_consistency,
            )

            # ── Decision (FR-7.4) ──────────────────────────────────────────────
            gold_price = await get_gold_price()
            decision_result = decide(fusion, gold_price)

            # ── Explanation (FR-9.2) ───────────────────────────────────────────
            try:
                decision_result.why = await explain(fusion, decision_result)
            except Exception as e:
                log.warning("pipeline.explain_failed", error=str(e))
                decision_result.why = ["Analysis complete. Visit a branch for verification."]

            # ── Build rationale JSON for Result screen ─────────────────────────
            rationale = {
                "headline": decision_result.headline,
                "next_steps_md": decision_result.next_steps_md,
                "ltv_applied": decision_result.ltv_applied,
                "weight_g": fusion.weight_g.model_dump(),
                "purity": fusion.purity.model_dump(),
                "authenticity_risk": fusion.authenticity_risk.model_dump(),
                "flags": fusion.flags,
                "evidence": [e.model_dump() for e in fusion.evidence],
            }

            # ── Persist ────────────────────────────────────────────────────────
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

        await asyncio.wait_for(_execute(), timeout=180.0)

    except Exception as exc:
        log.exception("pipeline.error", error=str(exc))
        await _mark_error(assessment_id)
