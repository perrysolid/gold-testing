"""FR-2, FR-4, FR-7: Assessment lifecycle routes.

POST /assess/start  → returns assessment_id + upload URLs
POST /assess/submit → triggers ML pipeline
GET  /assess/{id}   → poll for result
GET  /assess/       → lender list (FR-10.1)
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.assess.orchestrator import run_pipeline
from app.assess.schemas import (
    AssessmentRequest,
    AssessmentStartResponse,
    DecisionResult,
)
from app.db.models import Assessment, get_session
from app.services.object_store import get_upload_url

router = APIRouter()


@router.post("/start", response_model=AssessmentStartResponse, status_code=201)
async def start_assessment(
    session: AsyncSession = Depends(get_session),
) -> AssessmentStartResponse:
    """FR-2: Create assessment record + return signed upload URLs."""
    assessment_id = str(uuid.uuid4())
    assessment = Assessment(id=assessment_id, user_id="demo-user")
    session.add(assessment)
    await session.commit()

    kinds = ["image_top", "image_side", "image_hallmark", "audio"]
    upload_urls = {k: await get_upload_url(assessment_id, k) for k in kinds}

    return AssessmentStartResponse(assessment_id=assessment_id, upload_urls=upload_urls)


@router.post("/submit", response_model=dict[str, str])
async def submit_assessment(
    body: AssessmentRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """FR-7: Validate submission, enqueue ML pipeline in background."""
    result = await session.exec(
        select(Assessment).where(Assessment.id == body.assessment_id)
    )
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
    """FR-9: Poll for assessment result with evidence."""
    result = await session.exec(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return {"assessment_id": assessment_id, "status": assessment.status, "decision": assessment.decision}


@router.get("/", response_model=list[dict])
async def list_assessments(
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """FR-10.1: Lender dashboard — list all assessments."""
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
