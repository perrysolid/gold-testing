"""FR-2, FR-4, FR-7: Assessment lifecycle routes.

POST /assess/start                → assessment_id + upload URLs
POST /assess/upload/{id}/{kind}   → multipart artifact upload
POST /assess/quality-check        → server-side image quality check (FR-2.4)
POST /assess/submit               → triggers ML pipeline
GET  /assess/{id}                 → poll for result (status + decision + fusion)
GET  /assess/                     → lender list (FR-10.1)
GET  /assess/{id}/pdf             → pre-approval PDF (FR-11.3)
"""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.assess.orchestrator import run_pipeline
from app.assess.schemas import AssessmentRequest, AssessmentStartResponse
from app.db.models import Assessment, Decision, get_session
from app.services.object_store import get_upload_url, save_artifact, sha256_hex

router = APIRouter()


@router.post("/start", response_model=AssessmentStartResponse, status_code=201)
async def start_assessment(
    session: AsyncSession = Depends(get_session),
) -> AssessmentStartResponse:
    """FR-2: Create assessment record + return upload URL map."""
    assessment_id = str(uuid.uuid4())
    assessment = Assessment(id=assessment_id, user_id="demo-user")
    session.add(assessment)
    await session.commit()

    kinds = ["image_top", "image_side", "image_hallmark", "audio"]
    upload_urls = {k: await get_upload_url(assessment_id, k) for k in kinds}
    return AssessmentStartResponse(assessment_id=assessment_id, upload_urls=upload_urls)


@router.post("/upload/{assessment_id}/{kind}", status_code=200)
async def upload_artifact(
    assessment_id: str,
    kind: str,
    file: UploadFile = File(...),
) -> dict[str, str]:
    """FR-2.5: Receive compressed image/audio from client and store locally."""
    allowed = {"image_top", "image_side", "image_hallmark", "audio"}
    if kind not in allowed:
        raise HTTPException(status_code=400, detail=f"Unknown kind: {kind}")
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")
    await save_artifact(assessment_id, kind, data)
    return {"status": "ok", "kind": kind}


@router.post("/quality-check")
async def quality_check(
    file: UploadFile = File(...),
) -> dict:
    """FR-2.4: Server-side image quality check before submission."""
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")
    from app.vision.quality import check_quality
    result = check_quality(data)
    return result.model_dump()


@router.post("/submit", response_model=dict[str, str])
async def submit_assessment(
    body: AssessmentRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """FR-7: Validate + enqueue ML pipeline via BackgroundTasks."""
    result = await session.exec(select(Assessment).where(Assessment.id == body.assessment_id))
    assessment = result.first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    assessment.status = "processing"
    assessment.item_type = body.item_declared.type
    session.add(assessment)
    await session.commit()

    background_tasks.add_task(run_pipeline, body.assessment_id, body)
    return {"assessment_id": body.assessment_id, "status": "processing"}


@router.get("/{assessment_id}", response_model=dict)
async def get_assessment(
    assessment_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """FR-9.1: Poll for result. Returns full rationale once done."""
    result = await session.exec(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    payload: dict = {
        "assessment_id": assessment_id,
        "status": assessment.status,
        "decision": assessment.decision,
        "item_type": assessment.item_type,
    }

    if assessment.status == "done":
        dec_result = await session.exec(select(Decision).where(Decision.assessment_id == assessment_id))
        dec = dec_result.first()
        if dec:
            rationale = json.loads(dec.rationale_json) if dec.rationale_json else {}
            payload.update({
                "max_loan_inr": dec.max_loan_inr,
                "explanation_md": dec.explanation_md,
                "why": dec.explanation_md.splitlines() if dec.explanation_md else [],
                "headline": rationale.get("headline", ""),
                "weight_g": rationale.get("weight_g"),
                "purity": rationale.get("purity"),
                "authenticity_risk": rationale.get("authenticity_risk"),
                "flags": rationale.get("flags", []),
                "evidence": rationale.get("evidence", []),
                "next_steps_md": rationale.get("next_steps_md", ""),
            })

    return payload


@router.get("/{assessment_id}/pdf")
async def download_pdf(
    assessment_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """FR-11.3: Generate and stream pre-approval PDF."""
    from app.assess.schemas import DecisionResult, GoldPriceSnapshot
    from app.services.pdf import generate_pre_approval_pdf
    from datetime import datetime, timezone

    result = await session.exec(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.first()
    if not assessment or assessment.status != "done":
        raise HTTPException(status_code=404, detail="Assessment not ready")

    dec_result = await session.exec(select(Decision).where(Decision.assessment_id == assessment_id))
    dec = dec_result.first()
    if not dec:
        raise HTTPException(status_code=404, detail="Decision not found")

    rationale = json.loads(dec.rationale_json) if dec.rationale_json else {}
    dr = DecisionResult(
        assessment_id=assessment_id,
        decision=dec.decision,
        headline=rationale.get("headline", dec.decision),
        max_loan_inr=dec.max_loan_inr,
        why=dec.explanation_md.splitlines() if dec.explanation_md else [],
        next_steps_md=rationale.get("next_steps_md", ""),
    )
    pdf_bytes = await generate_pre_approval_pdf(dr)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=aurum_{assessment_id[:8]}.pdf"},
    )


@router.get("/", response_model=list[dict])
async def list_assessments(
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """FR-10.1: Lender dashboard list."""
    results = await session.exec(select(Assessment).order_by(Assessment.created_at.desc()))  # type: ignore[arg-type]
    return [
        {
            "id": a.id,
            "status": a.status,
            "decision": a.decision,
            "item_type": a.item_type,
            "created_at": a.created_at.isoformat(),
        }
        for a in results.all()
    ]
