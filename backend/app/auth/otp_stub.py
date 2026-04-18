"""FR-1.1: OTP stub — always accepts OTP_DEV_BYPASS in dev.

Replace with a real SMS gateway (e.g., Twilio / Exotel) for production.
"""
from __future__ import annotations

import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# In-memory store for demo; swap with Redis in prod
_pending: dict[str, str] = {}


async def send_otp(phone: str) -> None:
    otp = settings.otp_dev_bypass
    _pending[phone] = otp
    logger.info("otp.sent", phone=phone[-4:], otp="[DEV]")


async def verify_otp(phone: str, otp: str) -> bool:
    expected = _pending.get(phone) or settings.otp_dev_bypass
    return otp == expected
