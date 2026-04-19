"""US-D1: Seed 3 demo assessment records for judging-room demo.

Run: python scripts/seed_demo_data.py
Creates pre-computed results for:
  1. demo-genuine-22k-chain  → PRE_APPROVE  ₹52,800
  2. demo-plated-bangle      → NEEDS_VERIFICATION
  3. demo-genuine-18k-ring   → PRE_APPROVE  ₹18,112

rationale_json must match the shape read by GET /assess/{id}:
  headline, next_steps_md, weight_g (WeightBand), purity (PurityBand),
  authenticity_risk, flags, evidence
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///./data/aurum.db")
os.environ.setdefault("GEMINI_MOCK", "true")
os.environ.setdefault("GOLD_API_PROVIDER", "mock")


def _rationale(demo: dict) -> str:
    return json.dumps({
        "headline": demo["headline"],
        "next_steps_md": demo["next_steps_md"],
        "weight_g": {
            "low": demo["weight_low"],
            "high": demo["weight_high"],
            "confidence": demo["weight_conf"],
            "method": "seed",
        },
        "purity": {
            "karat_low": demo["purity_karat"],
            "karat_high": demo["purity_karat"],
            "fineness_low": demo["fineness"],
            "fineness_high": demo["fineness"],
            "confidence": demo["purity_conf"],
            "primary_signal": "hallmark_ocr",
        },
        "authenticity_risk": {
            "level": demo["risk_level"],
            "score": demo["risk_score"],
        },
        "flags": demo["flags"],
        "evidence": [],
    })


DEMO_DECISIONS = [
    {
        "id": "demo-genuine-22k-chain",
        "item_type": "chain",
        "decision": "PRE_APPROVE",
        "headline": "Estimated 8–12 g, 22K, low risk",
        "next_steps_md": "Visit a branch within 14 days to complete physical verification and disbursal.",
        "weight_low": 8.0, "weight_high": 12.0, "weight_conf": 0.78,
        "purity_karat": 22, "fineness": 916, "purity_conf": 0.91,
        "risk_score": 0.12, "risk_level": "LOW",
        "max_loan_inr": 52_800,
        "flags": ["HALLMARK_VALID_BIS", "COIN_SCALE_DETECTED"],
        "why": [
            "- Valid BIS hallmark with readable 916 purity mark detected.",
            "- ArUco scale marker confirms weight estimate of 8–12 g (78% confidence).",
            "- Colour analysis consistent with 22K gold — warm yellow, low variance.",
            "- Audio tap test confirms solid karat metal, not hollow or plated.",
            "- Final valuation requires physical branch verification.",
        ],
    },
    {
        "id": "demo-plated-bangle",
        "item_type": "bangle",
        "decision": "NEEDS_VERIFICATION",
        "headline": "Estimated 15–22 g, purity unclear, medium risk",
        "next_steps_md": "Bring your jewellery to the nearest branch for expert verification.",
        "weight_low": 15.0, "weight_high": 22.0, "weight_conf": 0.55,
        "purity_karat": 18, "fineness": 750, "purity_conf": 0.50,
        "risk_score": 0.48, "risk_level": "MEDIUM",
        "max_loan_inr": None,
        "flags": ["HALLMARK_MISSING_CAPPED"],
        "why": [
            "- No BIS hallmark detected; purity cannot be confirmed from image alone.",
            "- Colour inconsistency: brassy tint detected near edges, suggesting possible plating.",
            "- Weight estimate of 15–22 g has lower confidence without scale reference.",
            "- Branch verification strongly recommended before loan approval.",
            "- Final valuation requires physical inspection at your nearest branch.",
        ],
    },
    {
        "id": "demo-genuine-18k-ring",
        "item_type": "ring",
        "decision": "PRE_APPROVE",
        "headline": "Estimated 3.5–5 g, 18K, low risk",
        "next_steps_md": "Visit a branch within 14 days to complete physical verification and disbursal.",
        "weight_low": 3.5, "weight_high": 5.0, "weight_conf": 0.74,
        "purity_karat": 18, "fineness": 750, "purity_conf": 0.82,
        "risk_score": 0.15, "risk_level": "LOW",
        "max_loan_inr": 18_112,
        "flags": ["HALLMARK_BIS_LOGO"],
        "why": [
            "- BIS logo detected with 750 purity mark (18K).",
            "- Ring weight estimated at 3.5–5.0 g based on segmentation and scale.",
            "- Even gold colour and surface uniformity indicate genuine 18K composition.",
            "- Maximum loan ₹18,112 calculated at 85% LTV on conservative weight.",
            "- Please visit a branch within 14 days to complete disbursal.",
        ],
    },
]


async def seed() -> None:
    from app.db.models import create_db_and_tables, Assessment, Decision, session_ctx
    from sqlmodel import select

    await create_db_and_tables()

    async with session_ctx() as session:
        for demo in DEMO_DECISIONS:
            existing = await session.exec(select(Assessment).where(Assessment.id == demo["id"]))
            if existing.first():
                print(f"  skip {demo['id']} (exists)")
                continue

            assessment = Assessment(
                id=demo["id"],
                user_id="demo-user",
                status="done",
                decision=demo["decision"],
                item_type=demo["item_type"],
            )
            session.add(assessment)

            decision = Decision(
                assessment_id=demo["id"],
                decision=demo["decision"],
                max_loan_inr=demo["max_loan_inr"],
                explanation_md="\n".join(demo["why"]),
                rationale_json=_rationale(demo),
            )
            session.add(decision)
            print(f"  seeded {demo['id']} → {demo['decision']}")

        await session.commit()
    print("Done. Demo data seeded.")


if __name__ == "__main__":
    asyncio.run(seed())
