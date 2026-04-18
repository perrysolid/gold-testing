"""FR-5.7: Scale estimation — ArUco DICT_5X5_50 → ₹10 coin → heuristic.

Returns pixels_per_mm ratio used by weight estimator.
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog

from app.assess.schemas import EvidenceItem

logger = structlog.get_logger()

COIN_DIAMETER_MM = 27.0   # ₹10 coin
ARUCO_SIDE_MM = 50.0      # printed 5 cm marker


async def detect_scale(image_bytes: bytes) -> EvidenceItem:
    """FR-5.7: Try ArUco → coin → heuristic. Returns pixels_per_mm + source."""
    import numpy as np
    import cv2

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = img.shape[:2]

    # 1) ArUco
    try:
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50)
        params = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, params)
        corners, ids, _ = detector.detectMarkers(gray)
        if ids is not None and len(ids) > 0:
            c = corners[0][0]
            side_px = float(np.linalg.norm(c[0] - c[1]))
            pixels_per_mm = side_px / ARUCO_SIDE_MM
            return EvidenceItem(
                id=f"ev_{uuid.uuid4().hex[:8]}",
                kind="scale_reference",
                payload={"type": "aruco", "pixels_per_mm": round(pixels_per_mm, 2)},
                confidence=0.97,
            )
    except Exception as e:
        logger.debug("scale.aruco_failed", error=str(e))

    # 2) ₹10 coin via Hough circles
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)
    circles = cv2.HoughCircles(
        blurred, cv2.HOUGH_GRADIENT, dp=1.2, minDist=30,
        param1=50, param2=30, minRadius=20, maxRadius=min(w, h) // 4
    )
    if circles is not None:
        r_px = float(circles[0][0][2])
        pixels_per_mm = (r_px * 2) / COIN_DIAMETER_MM
        return EvidenceItem(
            id=f"ev_{uuid.uuid4().hex[:8]}",
            kind="scale_reference",
            payload={"type": "coin_hough", "pixels_per_mm": round(pixels_per_mm, 2)},
            confidence=0.72,
        )

    # 3) Heuristic: assume ring ~20 mm diameter occupies ~15% frame width
    proxy_mm = 20.0
    pixels_per_mm = (w * 0.15) / proxy_mm
    return EvidenceItem(
        id=f"ev_{uuid.uuid4().hex[:8]}",
        kind="scale_reference",
        payload={"type": "heuristic", "pixels_per_mm": round(pixels_per_mm, 2)},
        confidence=0.35,
    )
