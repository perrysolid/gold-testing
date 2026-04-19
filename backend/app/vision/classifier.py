"""FR-5.1: Jewellery-type classifier.

Priority:
  1. Fine-tuned YOLOv8-cls model (when weights file exists)
  2. Gemini 2.5 Flash vision sanity check (§13.2) — best zero-shot accuracy
  3. Declared type from request (honest fallback at 0.4 confidence)

Non-jewellery gate: if the classifier concludes non_jewellery with
confidence ≥ NON_JEWELLERY_THRESHOLD the caller should reject the
assessment rather than continuing with fabricated evidence.
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog

from app.assess.schemas import EvidenceItem

logger = structlog.get_logger()

CLASSES = ["ring", "chain", "bangle", "earring", "pendant", "coin", "bar", "non_jewellery"]
NON_JEWELLERY_THRESHOLD = 0.55   # confidence above this → reject assessment

# §13.2 Gemini prompt — use "non_jewellery" consistently with CLASSES list
_GEMINI_CLASSIFY_PROMPT = """Analyse this image. Return JSON only:
{
  "item_type": "ring|chain|bangle|earring|pendant|coin|bar|non_jewellery|unknown",
  "apparent_karat_guess": "14K|18K|20K|22K|24K|unknown",
  "visual_flags": ["even_color","uneven_color","visible_scratches","worn_plating",
                   "greenish_tint","brassy_tint","hollow_looking","solid_looking"],
  "confidence": 0.0,
  "reasoning": "1-2 sentences"
}
Use "non_jewellery" if the image does NOT show a piece of gold/silver jewellery
(e.g. it shows a person, food, document, random object, etc.).
Do not include any other text."""

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
    """FR-5.1: Returns item_type evidence with confidence.

    Check ev.payload["class"] == "non_jewellery" after calling — if true and
    ev.confidence >= NON_JEWELLERY_THRESHOLD the assessment should be rejected.
    """
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

        # Accept non_jewellery explicitly so the orchestrator can gate on it
        if item_type in CLASSES:
            return EvidenceItem(
                id=ev_id,
                kind="item_type_classification",
                payload={
                    "class": item_type,
                    "source": "gemini_vision",
                    "karat_guess": karat_guess,
                    "visual_flags": flags,
                    "reasoning": gemini_result.get("reasoning", ""),
                },
                confidence=conf,
            )
        if item_type == "unknown":
            return EvidenceItem(
                id=ev_id,
                kind="item_type_classification",
                payload={
                    "class": declared_type,
                    "source": "gemini_vision_unknown",
                    "karat_guess": karat_guess,
                    "visual_flags": flags,
                    "reasoning": gemini_result.get("reasoning", ""),
                },
                confidence=min(conf, 0.45),
            )

    # ── 3. Content-based heuristic — detect non-gold colors ─────────────────
    # If image has no metallic/warm-yellow pixels, flag as suspicious
    non_jewellery_conf = _heuristic_non_jewellery(image_bytes)
    if non_jewellery_conf >= NON_JEWELLERY_THRESHOLD:
        logger.info("classifier.heuristic_non_jewellery", conf=non_jewellery_conf)
        return EvidenceItem(
            id=ev_id,
            kind="item_type_classification",
            payload={"class": "non_jewellery", "source": "color_heuristic"},
            confidence=non_jewellery_conf,
        )

    # ── 4. Declared type fallback ─────────────────────────────────────────────
    return EvidenceItem(
        id=ev_id,
        kind="item_type_classification",
        payload={"class": declared_type, "source": "declared_fallback"},
        confidence=0.40,
    )


def _heuristic_non_jewellery(image_bytes: bytes) -> float:
    """Return confidence [0,1] that the image does NOT contain gold/silver jewellery.

    Uses LAB colour space to detect metallic warm-yellow (gold) or neutral-bright
    (silver/white gold) pixels. If fewer than 5% of foreground pixels have
    metallic colour, returns elevated non-jewellery confidence.
    """
    try:
        import numpy as np
        import cv2

        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return 0.0

        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        L, a, b = cv2.split(lab)

        L_i = L.astype(np.int32)
        a_i = a.astype(np.int32)
        b_i = b.astype(np.int32)

        # Foreground = not near-white background
        foreground = L_i < 235
        fg_count = int(np.sum(foreground))
        if fg_count < 300:
            return 0.0

        # Gold 22K ≈ LAB L≈75 a≈133 b≈183 — very yellow (high b), NOT red (low a)
        # Skin    ≈ LAB L≈65 a≈153 b≈148 — fails because a too high
        # Orange  ≈ LAB L≈55 a≈163 b≈168 — fails because a too high
        gold_mask = foreground & (b_i > 158) & (a_i < 142) & (L_i > 70)

        # Silver/white gold: very bright + near-neutral hue
        silver_mask = (
            foreground & (L_i > 175)
            & (np.abs(a_i - 128) < 12) & (np.abs(b_i - 128) < 15)
        )

        # Specular highlights on metallic surfaces (tiny very-bright spots)
        specular_ratio = float(np.sum(L_i > 220)) / L_i.size

        metallic_ratio = (float(np.sum(gold_mask)) + float(np.sum(silver_mask))) / fg_count

        if metallic_ratio >= 0.03 or specular_ratio >= 0.008:
            return 0.0   # looks metallic

        # Scale 0→0.65 as metallic pixels approach 0
        conf = max(0.0, 0.65 * (1.0 - metallic_ratio / 0.03))
        return round(conf, 3)
    except Exception:
        return 0.0
