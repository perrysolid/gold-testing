"""FR-2.4: Image quality checks — blur, brightness, frame occupancy, content.

Called server-side on each uploaded image; results surfaced to client.
jewellery_ok: True if image appears to contain metallic/gold jewellery content.
"""
from __future__ import annotations

from pydantic import BaseModel


class QualityResult(BaseModel):
    bright_ok: bool
    sharp_ok: bool
    occupancy_ok: bool
    jewellery_ok: bool
    overall_ok: bool
    blur_score: float
    brightness_mean: float
    occupancy_ratio: float
    jewellery_reason: str = ""


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

    jewellery_ok, jewellery_reason = _check_jewellery_content(img)

    return QualityResult(
        bright_ok=40.0 <= brightness <= 240.0,
        sharp_ok=blur_score >= 100.0,
        occupancy_ok=occupancy >= 0.15,
        jewellery_ok=jewellery_ok,
        overall_ok=all([40.0 <= brightness <= 240.0, blur_score >= 100.0, occupancy >= 0.15]),
        blur_score=round(blur_score, 1),
        brightness_mean=round(brightness, 1),
        occupancy_ratio=round(occupancy, 3),
        jewellery_reason=jewellery_reason,
    )


def _check_jewellery_content(img_bgr: "np.ndarray") -> tuple[bool, str]:  # type: ignore[name-defined]
    """Heuristic: detect metallic gold/silver content distinct from skin/curtains.

    Key insight — LAB channel separation:
      Gold 22K  ≈ RGB(212,175,55)  → LAB L≈75 a≈133 b≈183  (high b, LOW a)
      Skin tone ≈ RGB(200,140,100) → LAB L≈65 a≈153 b≈148  (mod b, HIGH a)
      Orange    ≈ RGB(200,100,50)  → LAB L≈55 a≈163 b≈168  (mod b, VERY HIGH a)
      Silver    ≈ RGB(200,200,200) → LAB L≈80 a≈128 b≈128  (neutral a+b, very bright)

    Gold = high b (>158) AND low a (<142) AND moderate-high L (>70)
    Silver = very high L (>175) AND near-neutral a (±12) AND near-neutral b (±15)
    Metallic specular = tiny very-bright spots (L>220), present on any shiny metal

    Skin and curtains fail the gold gate because their a-channel is too high.
    """
    import numpy as np
    import cv2

    try:
        lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
        L, a, b = cv2.split(lab)

        L_i = L.astype(np.int32)
        a_i = a.astype(np.int32)
        b_i = b.astype(np.int32)

        # Foreground = not near-white background
        foreground = L_i < 235
        fg_count = int(np.sum(foreground))
        if fg_count < 300:
            return True, "mostly_white_background"

        # ── Gold mask: warm yellow, but NOT skin-red / orange-red ────────────
        # Gold has b > 158 (very yellow) AND a < 142 (not red)
        gold_mask = (
            foreground
            & (b_i > 158)
            & (a_i < 142)
            & (L_i > 70)
        )

        # ── Silver/white gold mask: bright + near-neutral hue ────────────────
        silver_mask = (
            foreground
            & (L_i > 175)
            & (np.abs(a_i - 128) < 12)
            & (np.abs(b_i - 128) < 15)
        )

        # ── Specular highlights: tiny very-bright spots on metallic surfaces ─
        # These appear on gold, silver, stainless steel but NOT on skin/fabric
        specular_mask = L_i > 220
        specular_ratio = float(np.sum(specular_mask)) / (L_i.size)

        gold_ratio    = float(np.sum(gold_mask))   / fg_count
        silver_ratio  = float(np.sum(silver_mask)) / fg_count
        metallic_ratio = gold_ratio + silver_ratio

        reason = (
            f"gold={gold_ratio:.3f} silver={silver_ratio:.3f} "
            f"specular={specular_ratio:.4f}"
        )

        # Pass if enough gold OR silver pixels, OR metallic specular glints
        if metallic_ratio >= 0.03:
            return True, reason
        if specular_ratio >= 0.008:   # ≥0.8% very-bright pixels = likely metallic
            return True, reason + " (specular)"

        return False, reason

    except Exception:
        return True, "check_failed_allowing"
