"""FR-5 data model — SQLModel over SQLite (dev) / Postgres (prod).

NFR-8: Deterministic IDs use uuid4 seeded at insert time.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, create_engine, text
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings

settings = get_settings()

_engine: Optional[AsyncEngine] = None


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        connect_args = {"check_same_thread": False} if "sqlite" in settings.db_url else {}
        _engine = create_async_engine(settings.db_url, connect_args=connect_args, echo=False)
    return _engine


async def get_session() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency — yields a session."""
    async with AsyncSession(_get_engine()) as session:
        yield session


from contextlib import asynccontextmanager  # noqa: E402

@asynccontextmanager
async def session_ctx():
    """Async context manager for use outside FastAPI dependency injection."""
    async with AsyncSession(_get_engine()) as session:
        yield session


async def create_db_and_tables() -> None:
    async with _get_engine().begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


# ── ORM models ────────────────────────────────────────────────────────────────

class User(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    phone_hash: str = Field(index=True)
    pan_hash: Optional[str] = None
    full_name_enc: Optional[str] = None
    role: str = Field(default="customer")  # customer | lender | admin
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Assessment(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    status: str = Field(default="pending")  # pending | processing | done | error
    decision: Optional[str] = None          # PRE_APPROVE | NEEDS_VERIFICATION | REJECT
    item_type: Optional[str] = None
    meta_json: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Artifact(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    assessment_id: str = Field(foreign_key="assessment.id", index=True)
    kind: str  # image_top | image_side | image_hallmark | audio
    object_key: str
    sha256: str
    size_bytes: int


class Evidence(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    assessment_id: str = Field(foreign_key="assessment.id", index=True)
    kind: str  # hallmark_ocr | segmentation_area_px | scale_reference | depth_volume_estimate | audio_tap
    payload_json: str
    confidence: float
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Decision(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    assessment_id: str = Field(foreign_key="assessment.id", unique=True)
    decision: str
    max_loan_inr: Optional[int] = None
    rule_version: str = "1.0"
    explanation_md: Optional[str] = None
    rationale_json: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditLog(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    actor: str
    action: str
    target_id: Optional[str] = None
    at: datetime = Field(default_factory=datetime.utcnow)
    details_json: Optional[str] = None


class GoldPrice(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    inr_per_gram_22k: float
    inr_per_gram_24k: float
    source: str
