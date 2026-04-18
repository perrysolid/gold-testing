"""FR-8.1: Fake hallmark detector — BIS logo proportions + HUID check."""
from __future__ import annotations

import re
from typing import Optional

from app.assess.schemas import EvidenceItem

HUID_RE = re.compile(r"^[A-Z0-9]{6}$")


def check_hallmark_sanity(ocr_ev: Optional[EvidenceItem]) -> tuple[float, list[str]]:
    """Returns (fake_hallmark_risk ∈ [0,1], flags)."""
    if not ocr_ev:
        return 0.0, []

    flags: list[str] = []
    risk = 0.0

    huid = ocr_ev.payload.get("huid")
    bis_logo = ocr_ev.payload.get("bis_logo", False)
    purity_mark = ocr_ev.payload.get("purity_mark")

    # HUID format mismatch
    if huid and not HUID_RE.match(huid.upper()):
        risk += 0.4
        flags.append("HUID_FORMAT_INVALID")

    # BIS logo claimed but purity mark missing
    if bis_logo and not purity_mark:
        risk += 0.3
        flags.append("BIS_LOGO_NO_PURITY")

    # Very low OCR confidence with bis logo claim
    if bis_logo and ocr_ev.confidence < 0.4:
        risk += 0.2
        flags.append("HALLMARK_LOW_CONF")

    if risk >= 0.6:
        flags.append("FAKE_HALLMARK_DETECTED")

    return min(risk, 1.0), flags
