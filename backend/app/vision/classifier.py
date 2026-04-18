"""FR-5.1: Jewellery-type classifier — YOLOv8n (8 classes).

Current implementation: rule-based stub (deviation logged).
Target: ultralytics YOLOv8n fine-tuned on Pushpalal/Enhancing_Jewelry_Recognition.
See docs/deviations.md for rationale.
"""
from __future__ import annotations

import structlog

from app.assess.schemas import EvidenceItem

logger = structlog.get_logger()

CLASSES = ["ring", "chain", "bangle", "earring", "pendant", "coin", "bar", "non_jewellery"]

_model = None  # lazy-loaded


def _load_model() -> object:
    global _model
    if _model is None:
        import os
        from app.config import get_settings
        settings = get_settings()
        path = settings.jewelry_cls_model
        if os.path.exists(path):
            from ultralytics import YOLO  # type: ignore[import]
            _model = YOLO(path)
            logger.info("classifier.loaded", path=path)
        else:
            logger.warning("classifier.model_not_found", path=path, fallback="rule_based")
    return _model


async def classify_type(image_bytes: bytes) -> EvidenceItem:
    """FR-5.1: Returns item_type with confidence. Falls back to 'ring' at 0.4 conf."""
    import uuid
    model = _load_model()

    if model is not None:
        import numpy as np
        import cv2
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        results = model.predict(img, imgsz=640, verbose=False)
        # Classification result
        if results and len(results[0].probs) > 0:
            probs = results[0].probs.data.cpu().numpy()
            idx = int(probs.argmax())
            return EvidenceItem(
                id=f"ev_{uuid.uuid4().hex[:8]}",
                kind="item_type_classification",
                payload={"class": CLASSES[idx], "probs": probs.tolist()},
                confidence=float(probs[idx]),
            )

    # Rule-based fallback
    return EvidenceItem(
        id=f"ev_{uuid.uuid4().hex[:8]}",
        kind="item_type_classification",
        payload={"class": "ring", "source": "rule_based_fallback"},
        confidence=0.4,
    )
