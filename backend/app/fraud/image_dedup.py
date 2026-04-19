"""FR-8.3: Image deduplication — perceptual hash against prior submissions."""
from __future__ import annotations

import hashlib

import structlog

logger = structlog.get_logger()

# In-memory for demo; swap with Redis SET in prod
_seen_hashes: set[str] = set()


def check_dedup(image_bytes: bytes) -> tuple[float, list[str]]:
    """FR-8.3: Returns (duplicate_risk, flags). Uses MD5 of first 8KB as proxy pHash."""
    try:
        # Sample first 8 KB — cheap proxy for perceptual duplicate in demo
        phash_str = hashlib.md5(image_bytes[:8192]).hexdigest()
        if phash_str in _seen_hashes:
            logger.warning("dedup.duplicate_detected", phash=phash_str[:8])
            return 1.0, ["DUPLICATE_SUBMISSION"]
        _seen_hashes.add(phash_str)
        return 0.0, []
    except Exception as e:
        logger.debug("dedup.failed", error=str(e))
        return 0.0, []
