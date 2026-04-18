"""FR-6.2: Purity classifier — hallmark-first stacking.

FR-7.3: Valid BIS+HUID boosts confidence +0.2 (cap 0.95).
         Missing hallmark on claimed 22K caps at 0.55.
"""
from __future__ import annotations

from typing import Optional

from app.assess.schemas import EvidenceItem, PurityBand

# Purity mark → (karat_low, karat_high, fineness_low, fineness_high)
PURITY_MAP: dict[str, tuple[int, int, int, int]] = {
    "999": (24, 24, 999, 999),
    "958": (23, 23, 958, 958),
    "916": (22, 22, 916, 916),
    "875": (20, 22, 875, 916),
    "750": (18, 18, 750, 750),
    "585": (14, 14, 585, 585),
    "375": (9,  9,  375, 375),
}

KARAT_STAMP_MAP: dict[str, str] = {
    "24k": "999", "24K": "999",
    "22k": "916", "22K": "916",
    "18k": "750", "18K": "750",
    "14k": "585", "14K": "585",
    "bis": "916",
}


def estimate_purity(
    ocr_ev: Optional[EvidenceItem],
    audio_ev: Optional[EvidenceItem],
    declared_stamp: Optional[str],
    flags: list[str],
) -> PurityBand:
    """FR-6.2: Returns PurityBand from stacked evidence."""
    # Default fallback band
    default = PurityBand(
        karat_low=18, karat_high=22, fineness_low=750, fineness_high=916,
        confidence=0.30, primary_signal="default",
    )

    # ── 1. Hallmark OCR (highest weight — §9.3.1 purity_weights) ─────────────
    hallmark_band: Optional[PurityBand] = None
    hallmark_conf = 0.0

    if ocr_ev:
        purity_mark = ocr_ev.payload.get("purity_mark")
        bis_logo = ocr_ev.payload.get("bis_logo", False)
        huid_valid = ocr_ev.payload.get("huid_valid", False)
        ocr_conf = float(ocr_ev.confidence)

        if purity_mark and purity_mark in PURITY_MAP:
            kl, kh, fl, fh = PURITY_MAP[purity_mark]
            hallmark_conf = ocr_conf

            # FR-7.3: BIS+HUID boost
            if bis_logo and huid_valid:
                hallmark_conf = min(hallmark_conf + 0.20, 0.95)
                flags.append("HALLMARK_VALID_BIS")
            elif bis_logo:
                hallmark_conf = min(hallmark_conf + 0.10, 0.85)
                flags.append("HALLMARK_BIS_LOGO")

            hallmark_band = PurityBand(
                karat_low=kl, karat_high=kh, fineness_low=fl, fineness_high=fh,
                confidence=round(hallmark_conf, 3),
                primary_signal="hallmark_ocr",
            )

    # ── 2. Self-report stamp (weight 0.10) ────────────────────────────────────
    declared_band: Optional[PurityBand] = None
    if declared_stamp:
        normalised = declared_stamp.strip().upper().replace(" ", "")
        mapped = KARAT_STAMP_MAP.get(normalised, normalised)
        if mapped in PURITY_MAP:
            kl, kh, fl, fh = PURITY_MAP[mapped]
            declared_band = PurityBand(
                karat_low=kl, karat_high=kh, fineness_low=fl, fineness_high=fh,
                confidence=0.30, primary_signal="self_report",
            )

    # ── 3. Audio boost (weight 0.20) ──────────────────────────────────────────
    audio_boost = 0.0
    if audio_ev and audio_ev.payload.get("class") == "solid_karat":
        audio_boost = 0.10 * audio_ev.confidence

    # ── Fuse ──────────────────────────────────────────────────────────────────
    if hallmark_band and hallmark_conf >= 0.5:
        result = hallmark_band.model_copy(
            update={"confidence": round(min(hallmark_band.confidence + audio_boost, 0.95), 3)}
        )
        # FR-7.3: No hallmark but claimed 22K caps at 0.55
        return result

    if declared_band:
        declared_22k = declared_band.karat_high >= 22
        no_valid_hallmark = hallmark_band is None or hallmark_conf < 0.5
        conf = min(declared_band.confidence + audio_boost, 0.55 if (declared_22k and no_valid_hallmark) else 0.70)
        flags.append("HALLMARK_MISSING_CAPPED")
        return declared_band.model_copy(update={"confidence": round(conf, 3)})

    return default
