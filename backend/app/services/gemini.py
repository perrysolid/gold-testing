"""FR-9.2: Gemini 2.5 Flash integration — OCR fallback + explanation.

Prompts from §13 of IMPLEMENTATION_PLAN.
NFR-9: Falls back to template text when API is down or GEMINI_MOCK=true.
Rule: ≤ 2 Gemini calls per assessment (hallmark fallback + explanation).
"""
from __future__ import annotations

import json
from typing import Any, Optional

import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# §13.1
_HALLMARK_OCR_PROMPT = """You are an OCR assistant for Indian gold jewellery hallmarks.
The image shows a small stamped region on gold. Possible contents:
- BIS logo (triangle with dot)
- Purity mark: one of 916, 750, 585, 999, 875, 958, 375
- HUID: exactly 6 alphanumeric characters
- Jeweller ID (short alphanumeric)

Return strict JSON:
{
  "bis_logo_present": bool,
  "purity_mark": "916 or null",
  "huid": "AB12CD or null",
  "jeweller_id": "string or null",
  "reading_confidence": 0.0,
  "notes": "string"
}
Do not include any other text. If nothing is legible, return all nulls and confidence 0."""

# §13.3
_EXPLANATION_PROMPT = """You are a calm, plain-English financial assistant for an Indian NBFC customer.
Given this structured assessment JSON, write 3-5 short bullets (max 18 words each)
explaining the decision. Do NOT invent numbers. Use Indian English. Mention that
final valuation requires branch verification.

INPUT:
{fusion_json}

OUTPUT format — a JSON array of strings, nothing else."""


async def ocr_hallmark_fallback(
    image_bytes: bytes, bbox: list[int]
) -> Optional[dict[str, Any]]:
    """FR-5.4: Gemini OCR fallback when PaddleOCR confidence < 0.6."""
    if settings.gemini_mock or not settings.gemini_api_key:
        logger.info("gemini.ocr_mock")
        return {
            "bis_logo_present": False,
            "purity_mark": None,
            "huid": None,
            "jeweller_id": None,
            "reading_confidence": 0.3,
            "notes": "mock response",
        }
    try:
        import base64
        from google import genai  # type: ignore[import]
        from google.genai import types  # type: ignore[import]

        client = genai.Client(api_key=settings.gemini_api_key)
        b64 = base64.b64encode(image_bytes).decode()
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                _HALLMARK_OCR_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=256,
            ),
        )
        logger.info("gemini.ocr_tokens", tokens=response.usage_metadata.total_token_count)
        return json.loads(response.text)
    except Exception as e:
        logger.warning("gemini.ocr_failed", error=str(e))
        return None


async def explain(fusion: Any, decision: Any) -> list[str]:
    """FR-9.2: Generate customer-facing explanation bullets."""
    if settings.gemini_mock or not settings.gemini_api_key:
        return _template_explanation(fusion, decision)
    try:
        from google import genai  # type: ignore[import]
        from google.genai import types  # type: ignore[import]

        fusion_dict = fusion.model_dump()
        prompt = _EXPLANATION_PROMPT.format(fusion_json=json.dumps(fusion_dict, indent=2))
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=512,
            ),
        )
        logger.info("gemini.explain_tokens", tokens=response.usage_metadata.total_token_count)
        bullets = json.loads(response.text)
        return bullets if isinstance(bullets, list) else _template_explanation(fusion, decision)
    except Exception as e:
        logger.warning("gemini.explain_failed", error=str(e))
        return _template_explanation(fusion, decision)


def _template_explanation(fusion: Any, decision: Any) -> list[str]:
    """NFR-9: Template fallback for explanation when Gemini is unavailable."""
    bullets = []
    ocr_ev = next((e for e in fusion.evidence if e.kind == "hallmark_ocr"), None)
    if ocr_ev and ocr_ev.payload.get("purity_mark"):
        bullets.append(f"Hallmark stamp {ocr_ev.payload['purity_mark']} was detected with BIS logo present.")
    else:
        bullets.append("No clear BIS hallmark was detected; purity estimated from other signals.")

    bullets.append(
        f"Estimated weight is {fusion.weight_g.low}–{fusion.weight_g.high} g "
        f"({round(fusion.weight_g.confidence * 100)}% confidence) based on image analysis."
    )
    bullets.append(
        f"Authenticity risk is {fusion.authenticity_risk.level.lower()} based on colour and surface analysis."
    )
    if decision.max_loan_inr:
        bullets.append(f"Maximum eligible loan is ₹{decision.max_loan_inr:,} at {int((decision.ltv_applied or 0.75) * 100)}% LTV.")
    bullets.append("Final valuation requires physical inspection at your nearest branch.")
    return bullets
