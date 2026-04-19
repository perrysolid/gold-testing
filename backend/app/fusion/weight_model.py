"""FR-6.1: Weight estimator — LightGBM + rule-based fallback.

NFR-6.3: Returns WeightBand (low, high, confidence), never a point estimate.
"""
from __future__ import annotations

import math
import os
import pickle
from typing import Optional

import structlog

from app.assess.schemas import EvidenceItem, WeightBand

logger = structlog.get_logger()

# Physical density per karat (g/cm³)
DENSITY: dict[int, float] = {24: 19.32, 22: 17.7, 18: 15.5, 14: 13.0}

_lgbm: Optional[object] = None


def _load_lgbm() -> Optional[object]:
    global _lgbm
    if _lgbm is None:
        from app.config import get_settings
        path = get_settings().weight_model
        if os.path.exists(path):
            with open(path, "rb") as f:
                _lgbm = pickle.load(f)
            logger.info("weight_model.lgbm_loaded", path=path)
        else:
            logger.warning("weight_model.not_found", path=path, fallback="rule_based")
    return _lgbm


def estimate_weight(
    seg_ev: Optional[EvidenceItem],
    scale_ev: Optional[EvidenceItem],
    depth_ev: Optional[EvidenceItem],
    item_type: str,
    purity_karat: int,
    declared_weight_g: Optional[float],
    flags: list[str],
) -> WeightBand:
    """FR-6.1: Returns weight band (low, high, confidence)."""
    density = DENSITY.get(purity_karat, DENSITY[22])

    volume_cm3: Optional[float] = None
    method = "rule_based"
    base_conf = 0.4

    if depth_ev:
        volume_cm3 = float(depth_ev.payload.get("volume_cm3", 0))
        base_conf = depth_ev.confidence
        method = "depth+area"

    if volume_cm3 and volume_cm3 > 0:
        point_g = volume_cm3 * density
    else:
        # 2D area-only heuristic when depth unavailable
        area_px = float(seg_ev.payload.get("mask_area_px", 100_000)) if seg_ev else 100_000
        ppm = float(scale_ev.payload.get("pixels_per_mm", 10)) if scale_ev else 10.0
        area_mm2 = area_px / (ppm ** 2)
        thickness_mm = {"ring": 3.0, "chain": 2.0, "bangle": 4.0}.get(item_type, 2.5)
        volume_cm3 = (area_mm2 * thickness_mm) / 1000.0
        point_g = volume_cm3 * density
        base_conf = min(base_conf, 0.45)
        method = "2d_area_heuristic"

    # ±30% band (narrowed by LightGBM if available)
    band_factor = 0.30
    lgbm = _load_lgbm()
    if lgbm is not None:
        try:
            import numpy as np
            karat_keys = list(DENSITY.keys())
            feats = np.array([[
                float(seg_ev.payload.get("mask_area_px", 0)) if seg_ev else 0,
                float(depth_ev.payload.get("thickness_mm", 2.5)) if depth_ev else 2.5,
                float(DENSITY.get(purity_karat, 17.7)),
                float(karat_keys.index(purity_karat) if purity_karat in karat_keys else 1),
            ]])
            pred = lgbm.predict(feats)  # native booster predict
            band_factor = max(float(pred[0]), 0.10)
            base_conf = min(base_conf + 0.1, 0.85)
            method = "lightgbm"
        except Exception as e:
            logger.warning("weight_model.lgbm_inference_failed", error=str(e))

    low = max(point_g * (1 - band_factor), 0.5)
    high = point_g * (1 + band_factor)

    # FR-7.2: self-report conflict check
    if declared_weight_g is not None:
        if low <= declared_weight_g <= high:
            low = (low + declared_weight_g) / 2
            high = (high + declared_weight_g) / 2
            base_conf = min(base_conf + 0.10, 0.90)
        elif abs(declared_weight_g - point_g) / max(point_g, 1) > 0.5:
            flags.append("WEIGHT_INCONSISTENCY")

    return WeightBand(
        low=round(low, 1),
        high=round(high, 1),
        confidence=round(min(base_conf, 0.95), 3),
        method=method,
    )
