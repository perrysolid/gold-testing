"""FR-5.5: Plating / wear detector — LAB colour analysis + edge density.

Current implementation: classical CV rule-based (deviation logged).
Target: MobileNetV3 binary classifier on 500+ labelled samples.
"""
from __future__ import annotations

import uuid

import structlog

from app.assess.schemas import EvidenceItem

logger = structlog.get_logger()

# LAB thresholds empirically tuned for 22K gold (a* -5 to +10, b* 20 to 50)
LAB_A_MIN, LAB_A_MAX = -5.0, 15.0
LAB_B_MIN, LAB_B_MAX = 18.0, 55.0


async def detect_plating(image_bytes: bytes, seg_ev: EvidenceItem) -> EvidenceItem:
    """FR-5.5: Returns plating_risk ∈ [0,1]. Higher = more suspicious."""
    import numpy as np
    import cv2

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]

    bbox = seg_ev.payload.get("mask_bbox", [0, 0, w, h])
    x, y, bw, bh = bbox
    crop = img[y : y + bh, x : x + bw]

    if crop.size == 0:
        return EvidenceItem(
            id=f"ev_{uuid.uuid4().hex[:8]}",
            kind="plating_detection",
            payload={"plating_risk": 0.5, "source": "empty_crop"},
            confidence=0.3,
        )

    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB).astype(float)
    a_mean = float(lab[:, :, 1].mean()) - 128
    b_mean = float(lab[:, :, 2].mean()) - 128
    a_std = float(lab[:, :, 1].std())

    # Pure gold: low a* variance, b* in warm range
    a_anomaly = not (LAB_A_MIN <= a_mean <= LAB_A_MAX)
    b_anomaly = not (LAB_B_MIN <= b_mean <= LAB_B_MAX)
    colour_risk = (0.5 if a_anomaly else 0.0) + (0.4 if b_anomaly else 0.0) + min(a_std / 30, 0.1)

    # Edge density near mask boundary (plating scratches show base metal)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edge_density = float(edges.sum()) / (crop.shape[0] * crop.shape[1] * 255)
    edge_risk = min(edge_density * 10, 0.3)

    plating_risk = min(colour_risk + edge_risk, 1.0)
    confidence = 0.55  # honest cap per plan §10.4

    return EvidenceItem(
        id=f"ev_{uuid.uuid4().hex[:8]}",
        kind="plating_detection",
        payload={
            "plating_risk": round(plating_risk, 3),
            "lab_a_mean": round(a_mean, 2),
            "lab_b_mean": round(b_mean, 2),
            "edge_density": round(edge_density, 4),
            "source": "lab_rules",
        },
        confidence=confidence,
    )
