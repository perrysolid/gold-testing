"""FR-5.1: Jewellery-type classifier.

Priority:
  1. Fine-tuned YOLOv8-cls model (when weights file exists)
  2. Gemini 2.5 Flash vision sanity check (§13.2) — best zero-shot accuracy
  3. Declared type from request (honest fallback at 0.4 confidence)
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog

from app.assess.schemas import EvidenceItem

logger = structlog.get_logger()

CLASSES = ["ring", "chain", "bangle", "earring", "pendant", "coin", "bar", "non_jewellery"]

# §13.2 Gemini prompt
_GEMINI_CLASSIFY_PROMPT = """Analyse this image of a piece of jewellery. Return JSON only:
{
  "item_type": "ring|chain|bangle|earring|pendant|coin|bar|not_jewellery|unknown",
  "apparent_karat_guess": "14K|18K|20K|22K|24K|unknown",
  "visual_flags": ["even_color","uneven_color","visible_scratches","worn_plating",
                   "greenish_tint","brassy_tint","hollow_looking","solid_looking"],
  "confidence": 0.0,
  "reasoning": "1-2 sentences"
}"""

_yolo: Optional[object] = None


def _load_yolo() -> Optional[object]:
    global _yolo
    if _yolo is None:
        import os
        from app.config import get_settings
        path = get_settings().jewelry_cls_model
        if os.path.exists(path):
            from ultralytics import YOLO  # type: ignore[import]
            _yolo = YOLO(path)
            logger.info("classifier.yolo_loaded", path=path)
        else:
            logger.debug("classifier.yolo_not_found", path=path)
    return _yolo


async def _gemini_classify(image_bytes: bytes) -> Optional[dict]:
    """§13.2: Ask Gemini to classify the jewellery type."""
    from app.config import get_settings
    settings = get_settings()
    if settings.gemini_mock or not settings.gemini_api_key:
        return None
    try:
        import json
        from google import genai  # type: ignore[import]
        from google.genai import types  # type: ignore[import]

        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                _GEMINI_CLASSIFY_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=256,
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        logger.warning("classifier.gemini_failed", error=str(e))
        return None


async def classify_type(image_bytes: bytes, declared_type: str = "ring") -> EvidenceItem:
    """FR-5.1: Returns item_type evidence with confidence."""
    ev_id = f"ev_{uuid.uuid4().hex[:8]}"

    # ── 1. Fine-tuned YOLOv8 ─────────────────────────────────────────────────
    yolo = _load_yolo()
    if yolo is not None:
        try:
            import numpy as np
            import cv2
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            results = yolo.predict(img, imgsz=640, verbose=False)
            if results and hasattr(results[0], "probs") and results[0].probs is not None:
                probs = results[0].probs.data.cpu().numpy()
                idx = int(probs.argmax())
                conf = float(probs[idx])
                return EvidenceItem(
                    id=ev_id,
                    kind="item_type_classification",
                    payload={"class": CLASSES[idx], "source": "yolov8_finetuned"},
                    confidence=conf,
                )
        except Exception as e:
            logger.warning("classifier.yolo_inference_failed", error=str(e))

    # ── 2. Gemini vision (§13.2) ──────────────────────────────────────────────
    gemini_result = await _gemini_classify(image_bytes)
    if gemini_result:
        item_type = gemini_result.get("item_type", "unknown")
        conf = float(gemini_result.get("confidence", 0.7))
        flags = gemini_result.get("visual_flags", [])
        karat_guess = gemini_result.get("apparent_karat_guess", "unknown")
        if item_type in CLASSES or item_type == "unknown":
            return EvidenceItem(
                id=ev_id,
                kind="item_type_classification",
                payload={
                    "class": item_type if item_type != "unknown" else declared_type,
                    "source": "gemini_vision",
                    "karat_guess": karat_guess,
                    "visual_flags": flags,
                    "reasoning": gemini_result.get("reasoning", ""),
                },
                confidence=conf,
            )

    # ── 3. Declared type fallback ─────────────────────────────────────────────
    return EvidenceItem(
        id=ev_id,
        kind="item_type_classification",
        payload={"class": declared_type, "source": "declared_fallback"},
        confidence=0.40,
    )
