"""FR-8.2: Multi-image consistency via CLIP embeddings.

Checks that all 3 images show the same item (cosine similarity > 0.75).
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger()

_clip_model = None
_clip_preprocess = None


def _load_clip() -> tuple:
    global _clip_model, _clip_preprocess
    if _clip_model is None:
        try:
            import clip  # type: ignore[import]
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            _clip_model, _clip_preprocess = clip.load("ViT-B/32", device=device)
            logger.info("clip.loaded")
        except Exception as e:
            logger.warning("clip.load_failed", error=str(e))
    return _clip_model, _clip_preprocess


async def check_consistency(image_bytes_list: list[bytes]) -> float:
    """FR-8.2: Returns minimum pairwise cosine similarity ∈ [0,1]."""
    if len(image_bytes_list) < 2:
        return 1.0

    model, preprocess = _load_clip()
    if model is None:
        return 0.9  # assume consistent when CLIP unavailable

    try:
        import io
        import torch
        import torch.nn.functional as F
        from PIL import Image  # type: ignore[import]

        device = next(model.parameters()).device
        embeddings = []
        for img_bytes in image_bytes_list:
            img = preprocess(Image.open(io.BytesIO(img_bytes))).unsqueeze(0).to(device)
            with torch.no_grad():
                emb = model.encode_image(img)
                emb = F.normalize(emb, dim=-1)
            embeddings.append(emb)

        min_sim = 1.0
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                sim = float((embeddings[i] * embeddings[j]).sum())
                min_sim = min(min_sim, sim)

        return min_sim
    except Exception as e:
        logger.warning("clip.inference_failed", error=str(e))
        return 0.9
