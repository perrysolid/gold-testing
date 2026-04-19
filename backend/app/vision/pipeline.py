"""FR-5: Vision pipeline entry point — chains all modules in order.

Called by orchestrator with raw image bytes.
Returns a list of EvidenceItems; each module degrades gracefully.
"""
from __future__ import annotations

import time
from typing import Optional

import structlog

from app.assess.schemas import EvidenceItem

logger = structlog.get_logger()


async def run_vision(
    images: list[bytes],
    declared_type: str = "ring",
) -> list[EvidenceItem]:
    """
    Run the full vision chain on uploaded images.

    images[0] = top/primary view
    images[-1] = hallmark close-up (or same as [0] if only one image)

    Returns a flat list of EvidenceItems for the fusion engine.
    """
    if not images:
        return []

    primary = images[0]
    hallmark_img = images[-1]
    t0 = time.perf_counter()

    from app.vision.classifier import classify_type
    from app.vision.segmenter import segment
    from app.vision.scale import detect_scale
    from app.vision.hallmark_detector import detect_hallmark
    from app.vision.hallmark_ocr import ocr_hallmark
    from app.vision.plating_detector import detect_plating
    from app.vision.depth import estimate_depth

    evidence: list[EvidenceItem] = []

    # ── 1. Jewellery type (FR-5.1) ────────────────────────────────────────────
    type_ev = await classify_type(primary, declared_type=declared_type)
    evidence.append(type_ev)
    logger.debug("vision.type", value=type_ev.payload.get("class"), conf=type_ev.confidence)

    # ── 2. Segmentation (FR-5.2) ──────────────────────────────────────────────
    seg_ev = await segment(primary, type_ev)
    evidence.append(seg_ev)
    logger.debug("vision.seg", area=seg_ev.payload.get("mask_area_px"))

    # ── 3. Scale reference (FR-5.7) ───────────────────────────────────────────
    scale_ev = await detect_scale(primary)
    evidence.append(scale_ev)
    logger.debug("vision.scale", type=scale_ev.payload.get("type"), ppm=scale_ev.payload.get("pixels_per_mm"))

    # ── 4. Hallmark region + OCR (FR-5.3 / FR-5.4) ───────────────────────────
    hallmark_ev = await detect_hallmark(hallmark_img)
    evidence.append(hallmark_ev)

    ocr_ev = await ocr_hallmark(hallmark_img, hallmark_ev)
    evidence.append(ocr_ev)
    logger.debug("vision.ocr", purity=ocr_ev.payload.get("purity_mark"), bis=ocr_ev.payload.get("bis_logo"))

    # ── 5. Plating / wear (FR-5.5) ────────────────────────────────────────────
    plating_ev = await detect_plating(primary, seg_ev)
    evidence.append(plating_ev)
    logger.debug("vision.plating", risk=plating_ev.payload.get("plating_risk"))

    # ── 6. Depth → volume (FR-5.8) ────────────────────────────────────────────
    depth_ev = await estimate_depth(primary, scale_ev)
    evidence.append(depth_ev)
    logger.debug("vision.depth", vol=depth_ev.payload.get("volume_cm3"))

    elapsed = round((time.perf_counter() - t0) * 1000)
    logger.info("vision.pipeline_done", evidence_count=len(evidence), ms=elapsed)
    return evidence
