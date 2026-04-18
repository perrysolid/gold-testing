"""FR-1: Phone OTP auth routes.

FR-1.1: Phone + OTP login (OTP_DEV_BYPASS=123456 for demo).
FR-1.2: Minimal KYC capture stub.
FR-1.3: Consent endpoint with timestamped signature.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from pydantic import BaseModel, field_validator

from app.auth.otp_stub import verify_otp, send_otp
from app.config import get_settings
from app.db.models import User, get_session
from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter()
settings = get_settings()


class OTPRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) != 10:
            raise ValueError("Phone must be 10 digits")
        return digits


class OTPVerify(BaseModel):
    phone: str
    otp: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _make_token(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "role": role, "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


@router.post("/otp/send", status_code=202)
async def request_otp(body: OTPRequest) -> dict[str, str]:
    """FR-1.1: Dispatch OTP to phone. In dev, always succeeds."""
    await send_otp(body.phone)
    return {"detail": "OTP sent"}


@router.post("/otp/verify", response_model=TokenResponse)
async def verify_otp_and_login(
    body: OTPVerify,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """FR-1.1: Verify OTP, upsert user, return JWT."""
    if not await verify_otp(body.phone, body.otp):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OTP")

    phone_hash = hashlib.sha256(body.phone.encode()).hexdigest()
    # TODO [FR-1.2]: upsert user from DB; for scaffold, create in-memory
    from sqlmodel import select
    result = await session.exec(select(User).where(User.phone_hash == phone_hash))
    user = result.first()
    if not user:
        user = User(phone_hash=phone_hash)
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return TokenResponse(access_token=_make_token(user.id, user.role))
