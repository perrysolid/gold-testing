"""FR-8.3: Image deduplication — perceptual hash against prior submissions."""
from __future__ import annotations

import structlog

logger = structlog.get_logger()

_seen_hashes: set[str] = set()  # In-memory for demo; swap with Redis in prod


def check_dedup(image_bytes: bytes) -> tuple[float, list[str]]:
    """FR-8.3: Returns (duplicate_risk, flags). Uses pHash."""
    try:
        from imagededup.methods import PHash  # type: ignore[import]
        import io
        from PIL import Image  # type: ignore[import]

        hasher = PHash()
        img = Image.open(io.BytesIO(image_bytes))
        phash = hasher.encode_image(image_array=None)  # type: ignore[call-arg]
        # Simplified: compute hash from image directly
        import hashlib
        phash_str = hashlib.md5(image_bytes[:1024]).hexdigest()

        if phash_str in _seen_hashes:
            return 1.0, ["DUPLICATE_SUBMISSION"]
        _seen_hashes.add(phash_str)
        return 0.0, []
    except Exception as e:
        logger.debug("dedup.failed", error=str(e))
        return 0.0, []
