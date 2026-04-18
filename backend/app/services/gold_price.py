"""FR-11.1: Gold price service — GoldAPI.io / MetalpriceAPI / mock.

15-minute cache. Falls back to mock when API unreachable.
"""
from __future__ import annotations

import time
from typing import Optional

import httpx
import structlog

from app.assess.schemas import GoldPriceSnapshot
from app.config import get_settings
from datetime import datetime, timezone

logger = structlog.get_logger()
settings = get_settings()

_cache: Optional[tuple[GoldPriceSnapshot, float]] = None  # (price, fetched_epoch)


async def get_gold_price() -> GoldPriceSnapshot:
    global _cache
    now = time.time()
    if _cache and (now - _cache[1]) < settings.gold_price_cache_ttl_seconds:
        return _cache[0]

    price = await _fetch_price()
    _cache = (price, now)
    return price


async def _fetch_price() -> GoldPriceSnapshot:
    provider = settings.gold_api_provider

    if provider == "mock" or not settings.goldapi_key:
        return _mock_price()

    try:
        if provider == "goldapi":
            return await _goldapi()
        if provider == "metalpriceapi":
            return await _metalpriceapi()
    except Exception as e:
        logger.warning("gold_price.fetch_failed", provider=provider, error=str(e), fallback="mock")

    return _mock_price()


async def _goldapi() -> GoldPriceSnapshot:
    url = "https://www.goldapi.io/api/XAU/INR"
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.get(url, headers={"x-access-token": settings.goldapi_key})
        r.raise_for_status()
        data = r.json()
    # GoldAPI returns price_gram_24k in INR
    per_g_24k = float(data["price_gram_24k"])
    per_g_22k = per_g_24k * (916 / 999)
    return GoldPriceSnapshot(
        inr_per_g_22k=round(per_g_22k, 2),
        fetched_at=datetime.now(timezone.utc),
    )


async def _metalpriceapi() -> GoldPriceSnapshot:
    url = "https://api.metalpriceapi.com/v1/latest"
    params = {"api_key": settings.metalpriceapi_key, "base": "XAU", "currencies": "INR"}
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    # 1 troy oz = 31.1035 g
    inr_per_oz = float(data["rates"]["INR"])
    per_g_24k = inr_per_oz / 31.1035
    per_g_22k = per_g_24k * (916 / 999)
    return GoldPriceSnapshot(
        inr_per_g_22k=round(per_g_22k, 2),
        fetched_at=datetime.now(timezone.utc),
    )


def _mock_price() -> GoldPriceSnapshot:
    return GoldPriceSnapshot(
        inr_per_g_22k=settings.gold_price_mock_inr_per_g_22k,
        fetched_at=datetime.now(timezone.utc),
    )
