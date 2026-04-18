"""FR-5.3: Hallmark region detector — secondary YOLOv8 model.

Trained on 200–500 close-up hallmark crops.
Classes: bis_logo, purity_mark, huid_code, jeweller_id.
Fallback: returns full image crop at reduced confidence.
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog

from app.assess.schemas import EvidenceItem

logger = structlog.get_logger()

_model: Optional[object] = None


def _load_model() -> Optional[object]:
    global _model
    if _model is None:
        import os
        from app.config import get_settings
        path = get_settings().hallmark_detector_model
        if os.path.exists(path):
            from ultralytics import YOLO  # type: ignore[import]
            _model = YOLO(path)
            logger.info("hallmark_detector.loaded", path=path)
        else:
            logger.warning("hallmark_detector.not_found", path=path, fallback="centre_crop")
    return _model


async def detect_hallmark(image_bytes: bytes) -> EvidenceItem:
    """FR-5.3: Locate hallmark region. Returns crop coords + detection confidence."""
    import numpy as np
    import cv2

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]

    model = _load_model()
    if model is not None:
        results = model.predict(img, imgsz=640, conf=0.25, verbose=False)
        boxes = results[0].boxes
        if boxes and len(boxes):
            best = boxes[boxes.conf.argmax()]
            x1, y1, x2, y2 = [int(v) for v in best.xyxy[0].tolist()]
            return EvidenceItem(
                id=f"ev_{uuid.uuid4().hex[:8]}",
                kind="hallmark_region",
                payload={"bbox": [x1, y1, x2, y2], "class": int(best.cls[0])},
                confidence=float(best.conf[0]),
            )

    # Fallback: upper-right quadrant (common hallmark placement)
    crop_box = [w // 2, 0, w, h // 2]
    return EvidenceItem(
        id=f"ev_{uuid.uuid4().hex[:8]}",
        kind="hallmark_region",
        payload={"bbox": crop_box, "source": "heuristic_fallback"},
        confidence=0.3,
    )
