"""FR-5.4: Hallmark OCR — PaddleOCR primary, Gemini 2.5 Flash fallback.

Pipeline: crop → CLAHE → adaptive threshold → deskew → PaddleOCR.
If mean OCR confidence < 0.6, escalate to Gemini (see §13.1 prompt).
"""
from __future__ import annotations

import re
import uuid
from typing import Optional

import structlog

from app.assess.schemas import EvidenceItem

logger = structlog.get_logger()

VALID_PURITY_MARKS = {"916", "750", "585", "999", "875", "958", "375"}
HUID_RE = re.compile(r"^[A-Z0-9]{6}$")

_ocr: Optional[object] = None


def _load_ocr() -> Optional[object]:
    global _ocr
    if _ocr is None:
        try:
            from paddleocr import PaddleOCR  # type: ignore[import]
            _ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            logger.info("paddleocr.loaded")
        except ImportError:
            logger.warning("paddleocr.not_installed", fallback="gemini_only")
    return _ocr


def _preprocess_crop(crop: "np.ndarray") -> "np.ndarray":  # type: ignore[name-defined]
    import cv2
    import numpy as np
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    thresh = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    return thresh


async def ocr_hallmark(image_bytes: bytes, hallmark_ev: EvidenceItem) -> EvidenceItem:
    """FR-5.4: OCR the hallmark region. Returns purity_mark, huid, bis_logo status."""
    import numpy as np
    import cv2

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    bbox = hallmark_ev.payload.get("bbox", [0, 0, img.shape[1], img.shape[0]])
    x1, y1, x2, y2 = bbox
    crop = img[y1:y2, x1:x2]

    processed = _preprocess_crop(crop)
    ocr = _load_ocr()

    raw_text = ""
    ocr_conf = 0.0

    if ocr is not None:
        try:
            results = ocr.ocr(processed, cls=True)
            if results and results[0]:
                texts = [(line[1][0], line[1][1]) for line in results[0]]
                raw_text = " ".join(t for t, _ in texts)
                ocr_conf = sum(c for _, c in texts) / len(texts) if texts else 0.0
        except Exception as e:
            logger.warning("paddleocr.inference_failed", error=str(e))

    # Gemini fallback when confidence too low (FR-5.4 §10.3)
    gemini_used = False
    if ocr_conf < 0.6:
        from app.services.gemini import ocr_hallmark_fallback
        gemini_result = await ocr_hallmark_fallback(image_bytes, bbox)
        if gemini_result:
            purity_mark = gemini_result.get("purity_mark")
            huid = gemini_result.get("huid")
            bis_logo = gemini_result.get("bis_logo_present", False)
            conf = float(gemini_result.get("reading_confidence", 0.5))
            gemini_used = True
        else:
            purity_mark, huid, bis_logo, conf = None, None, False, 0.2
    else:
        # Parse from PaddleOCR raw text
        purity_mark = next((p for p in VALID_PURITY_MARKS if p in raw_text.replace(" ", "")), None)
        huid_match = HUID_RE.search(raw_text.replace(" ", "").upper())
        huid = huid_match.group() if huid_match else None
        bis_logo = "bis" in raw_text.lower() or "▲" in raw_text
        conf = ocr_conf

    return EvidenceItem(
        id=f"ev_{uuid.uuid4().hex[:8]}",
        kind="hallmark_ocr",
        payload={
            "raw_text": raw_text,
            "purity_mark": purity_mark,
            "huid": huid,
            "bis_logo": bis_logo,
            "gemini_used": gemini_used,
            "huid_valid": bool(huid and HUID_RE.match(huid)),
            "purity_valid": purity_mark in VALID_PURITY_MARKS if purity_mark else False,
        },
        confidence=conf,
    )
