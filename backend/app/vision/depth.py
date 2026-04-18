"""FR-5.8: Monocular depth estimation — MiDaS v2.1 small.

NFR-9: If MiDaS fails or depth variance is low (reflective gold),
       caps weight confidence at 0.55 and falls back to 2D area heuristic.
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog

from app.assess.schemas import EvidenceItem

logger = structlog.get_logger()

_midas: Optional[object] = None
_transform: Optional[object] = None


def _load_midas() -> tuple[Optional[object], Optional[object]]:
    global _midas, _transform
    if _midas is None:
        try:
            import torch
            import timm  # type: ignore[import]
            from app.config import get_settings
            model_type = get_settings().midas_model_type
            _midas = torch.hub.load("intel-isl/MiDaS", model_type, trust_repo=True)
            _midas.eval()
            transforms = torch.hub.load("intel-isl/MiDaS", "transforms", trust_repo=True)
            _transform = transforms.small_transform
            logger.info("midas.loaded", model=model_type)
        except Exception as e:
            logger.warning("midas.load_failed", error=str(e), fallback="2d_heuristic")
    return _midas, _transform


async def estimate_depth(image_bytes: bytes, scale_ev: EvidenceItem) -> EvidenceItem:
    """FR-5.8: Returns volume estimate in cm³ using MiDaS depth + scale."""
    import numpy as np
    import cv2

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    pixels_per_mm = float(scale_ev.payload.get("pixels_per_mm", 10.0))
    scale_conf = scale_ev.confidence

    midas, transform = _load_midas()

    if midas is not None and transform is not None:
        try:
            import torch
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            midas.to(device)
            input_batch = transform(rgb).to(device)
            with torch.no_grad():
                depth = midas(input_batch)
                depth = torch.nn.functional.interpolate(
                    depth.unsqueeze(1), size=rgb.shape[:2], mode="bicubic", align_corners=False
                ).squeeze()
            depth_np = depth.cpu().numpy()
            depth_std = float(depth_np.std())

            # Low variance = reflective surface → reduce confidence
            conf = 0.65 if depth_std > 50 else 0.45

            # Convert relative depth range to physical thickness proxy
            depth_range = float(depth_np.max() - depth_np.min())
            thickness_mm = min(depth_range / (pixels_per_mm * 5), 8.0)  # cap at 8 mm
            area_mm2 = float((depth_np > depth_np.mean()).sum()) / (pixels_per_mm ** 2)
            volume_cm3 = (area_mm2 * thickness_mm) / 1000.0

            return EvidenceItem(
                id=f"ev_{uuid.uuid4().hex[:8]}",
                kind="depth_volume_estimate",
                payload={
                    "volume_cm3": round(volume_cm3, 3),
                    "thickness_mm": round(thickness_mm, 2),
                    "depth_std": round(depth_std, 2),
                    "method": "midas",
                },
                confidence=conf * scale_conf,
            )
        except Exception as e:
            logger.warning("midas.inference_failed", error=str(e), fallback="2d")

    # 2D area heuristic fallback (NFR-9)
    h, w = img.shape[:2]
    area_mm2 = (h * w * 0.15) / (pixels_per_mm ** 2)
    thickness_mm = 2.5  # typical chain/ring
    volume_cm3 = (area_mm2 * thickness_mm) / 1000.0
    return EvidenceItem(
        id=f"ev_{uuid.uuid4().hex[:8]}",
        kind="depth_volume_estimate",
        payload={"volume_cm3": round(volume_cm3, 3), "method": "2d_heuristic"},
        confidence=0.35,
    )
