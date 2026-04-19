"""FR-2.4: Image quality checks — blur, brightness, frame occupancy.

Called server-side on each uploaded image; results surfaced to client.
"""
from __future__ import annotations

from pydantic import BaseModel


class QualityResult(BaseModel):
    bright_ok: bool
    sharp_ok: bool
    occupancy_ok: bool
    overall_ok: bool
    blur_score: float
    brightness_mean: float
    occupancy_ratio: float


def check_quality(image_bytes: bytes) -> QualityResult:
    """FR-2.4: Returns per-metric bool + numeric scores."""
    import numpy as np
    import cv2

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())

    # Simple occupancy: assume foreground pixels are > otsu threshold
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    occupancy = float(thresh.sum() / 255) / (thresh.shape[0] * thresh.shape[1])

    return QualityResult(
        bright_ok=40.0 <= brightness <= 240.0,
        sharp_ok=blur_score >= 100.0,
        occupancy_ok=occupancy >= 0.15,
        overall_ok=all([40.0 <= brightness <= 240.0, blur_score >= 100.0, occupancy >= 0.15]),
        blur_score=round(blur_score, 1),
        brightness_mean=round(brightness, 1),
        occupancy_ratio=round(occupancy, 3),
    )
