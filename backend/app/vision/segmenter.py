"""FR-5.2: Instance segmentation — SAM2 tiny seeded by YOLO bbox.

Fallback: GrabCut seeded by centre crop when SAM2 not loaded.
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog

from app.assess.schemas import EvidenceItem

logger = structlog.get_logger()

_sam2 = None


def _load_sam2() -> object:
    global _sam2
    if _sam2 is None:
        import os
        from app.config import get_settings
        cfg, ckpt = get_settings().sam2_config, get_settings().sam2_checkpoint
        if os.path.exists(ckpt):
            try:
                from sam2.build_sam import build_sam2  # type: ignore[import]
                from sam2.sam2_image_predictor import SAM2ImagePredictor  # type: ignore[import]
                sam = build_sam2(cfg, ckpt)
                _sam2 = SAM2ImagePredictor(sam)
                logger.info("sam2.loaded", checkpoint=ckpt)
            except Exception as e:
                logger.warning("sam2.load_failed", error=str(e), fallback="grabcut")
        else:
            logger.warning("sam2.checkpoint_not_found", path=ckpt, fallback="grabcut")
    return _sam2


async def segment(image_bytes: bytes, type_evidence: EvidenceItem) -> EvidenceItem:
    """FR-5.2: Returns segmentation mask area + bbox."""
    import numpy as np
    import cv2

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]

    sam2 = _load_sam2()
    if sam2 is not None:
        try:
            import torch
            sam2.set_image(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            # Use centre-point prompt for zero-shot segmentation
            cx, cy = w // 2, h // 2
            masks, scores, _ = sam2.predict(
                point_coords=np.array([[cx, cy]]),
                point_labels=np.array([1]),
                multimask_output=False,
            )
            mask = masks[0].astype(np.uint8)
            area_px = int(mask.sum())
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            bbox = list(cv2.boundingRect(contours[0])) if contours else [0, 0, w, h]
            return EvidenceItem(
                id=f"ev_{uuid.uuid4().hex[:8]}",
                kind="segmentation_area_px",
                payload={"mask_area_px": area_px, "mask_bbox": bbox, "method": "sam2"},
                confidence=float(scores[0]),
            )
        except Exception as e:
            logger.warning("sam2.inference_failed", error=str(e), fallback="grabcut")

    # GrabCut fallback
    mask = np.zeros((h, w), np.uint8)
    rect = (int(w * 0.1), int(h * 0.1), int(w * 0.8), int(h * 0.8))
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(img, mask, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
    grab_mask = np.where((mask == 2) | (mask == 0), 0, 1).astype(np.uint8)
    area_px = int(grab_mask.sum())
    return EvidenceItem(
        id=f"ev_{uuid.uuid4().hex[:8]}",
        kind="segmentation_area_px",
        payload={"mask_area_px": area_px, "mask_bbox": list(rect), "method": "grabcut_fallback"},
        confidence=0.5,
    )
