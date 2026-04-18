"""FR-5: Vision pipeline unit tests using synthetic fixture images (§16)."""
from __future__ import annotations

import io
import struct
import zlib

import pytest


def _make_png(w: int = 100, h: int = 100, r: int = 200, g: int = 180, b: int = 80) -> bytes:
    """Create a minimal solid-colour PNG without Pillow."""
    raw = bytes([0, r, g, b] * w) * h  # RGBA rows
    scanlines = b"".join(b"\x00" + bytes([r, g, b]) * w for _ in range(h))
    compressed = zlib.compress(scanlines, 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr_data = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr_data)
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )


GOLD_PNG = _make_png(r=212, g=175, b=55)   # gold-ish colour
DARK_PNG = _make_png(r=20, g=20, b=20)     # too dark


def test_quality_bright_ok() -> None:
    from app.vision.quality import check_quality
    q = check_quality(GOLD_PNG)
    assert q.bright_ok


def test_quality_dark_fails() -> None:
    from app.vision.quality import check_quality
    q = check_quality(DARK_PNG)
    assert not q.bright_ok


def test_quality_returns_occupancy_ratio() -> None:
    from app.vision.quality import check_quality
    q = check_quality(GOLD_PNG)
    assert 0 <= q.occupancy_ratio <= 1


@pytest.mark.asyncio
async def test_scale_returns_evidence() -> None:
    from app.vision.scale import detect_scale
    ev = await detect_scale(GOLD_PNG)
    assert ev.kind == "scale_reference"
    assert ev.payload["pixels_per_mm"] > 0
    assert 0 <= ev.confidence <= 1


@pytest.mark.asyncio
async def test_plating_returns_risk() -> None:
    from app.vision.plating_detector import detect_plating
    from app.assess.schemas import EvidenceItem
    seg_ev = EvidenceItem(
        id="t1", kind="segmentation_area_px",
        payload={"mask_area_px": 5000, "mask_bbox": [10, 10, 80, 80]},
        confidence=0.8,
    )
    ev = await detect_plating(GOLD_PNG, seg_ev)
    assert ev.kind == "plating_detection"
    assert 0 <= ev.payload["plating_risk"] <= 1
