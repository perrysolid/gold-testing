"""Generate demo assets for hackathon presentation.

Creates per-item-type top/side/hallmark images for all 6 item types:
  ring, chain, bangle, earring, pendant, coin

Output structure:
  demo_assets/images/
    ring_top.jpg, ring_side.jpg
    chain_top.jpg, chain_side.jpg
    bangle_top.jpg, bangle_side.jpg
    earring_top.jpg, earring_side.jpg
    pendant_top.jpg, pendant_side.jpg
    coin_top.jpg, coin_side.jpg
    hallmark_916.jpg, hallmark_750.jpg
  demo_assets/audio/
    tap_solid_22k.wav, tap_hollow_bangle.wav, tap_plated.wav, tap_solid_18k.wav

Run: python scripts/generate_demo_assets.py
"""
from __future__ import annotations
import math
import wave
from pathlib import Path
import numpy as np

OUT_DIR = Path("demo_assets")
IMG_DIR = OUT_DIR / "images"
AUD_DIR = OUT_DIR / "audio"
IMG_DIR.mkdir(parents=True, exist_ok=True)
AUD_DIR.mkdir(parents=True, exist_ok=True)

rng = np.random.default_rng(42)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _save_jpg(arr: np.ndarray, path: Path, quality: int = 95) -> None:
    import cv2
    cv2.imwrite(str(path), arr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    print(f"  saved {path} ({arr.shape[1]}x{arr.shape[0]})")


def _canvas(size: int = 480) -> np.ndarray:
    return np.full((size, size, 3), 248, dtype=np.uint8)


def _gold_bgr(karat: int = 22, noise: float = 0.0) -> tuple[int, int, int]:
    base = {24: (55, 190, 215), 22: (50, 175, 212), 18: (80, 185, 205), 14: (100, 180, 195)}
    b, g, r = base.get(karat, base[22])
    if noise > 0:
        b = int(np.clip(b + rng.normal(0, noise * 30), 0, 255))
        g = int(np.clip(g + rng.normal(0, noise * 15), 0, 255))
        r = int(np.clip(r + rng.normal(0, noise * 20), 0, 255))
    return b, g, r


def _shadow(bgr: tuple[int, int, int], factor: int = 45) -> tuple[int, int, int]:
    return tuple(max(c - factor, 0) for c in bgr)  # type: ignore


def _specular(img: np.ndarray, cx: int, cy: int, r: int = 7) -> np.ndarray:
    import cv2
    ov = img.copy()
    cv2.ellipse(ov, (cx, cy), (r, r // 2), -30, 0, 360, (255, 255, 255), -1)
    return cv2.addWeighted(ov, 0.55, img, 0.45, 0)


def _stamp(img: np.ndarray, text: str, x: int, y: int, scale: float = 0.35) -> np.ndarray:
    import cv2
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (40, 40, 40), 1, cv2.LINE_AA)
    return img


# ── Ring ──────────────────────────────────────────────────────────────────────

def make_ring_top(karat: int = 22) -> np.ndarray:
    import cv2
    img = _canvas()
    H, W = img.shape[:2]
    col = _gold_bgr(karat, noise=0.1)
    shd = _shadow(col)
    cx, cy, outer_r, thick = W // 2, H // 2, 140, 30
    cv2.circle(img, (cx + 4, cy + 4), outer_r, shd, thick + 2)
    cv2.circle(img, (cx, cy), outer_r, col, thick)
    for deg in range(200, 340, 18):
        a = math.radians(deg)
        hx = int(cx + (outer_r - thick // 2) * math.cos(a))
        hy = int(cy + (outer_r - thick // 2) * math.sin(a))
        cv2.circle(img, (hx, hy), 4, (255, 255, 215), -1)
    stamp = "750" if karat == 18 else "916"
    img = _stamp(img, f"BIS {stamp}", cx - 20, cy + 4)
    return img


def make_ring_side(karat: int = 22) -> np.ndarray:
    """Side profile — shows band width and shank."""
    import cv2
    img = _canvas()
    H, W = img.shape[:2]
    col = _gold_bgr(karat, noise=0.1)
    shd = _shadow(col)
    cx, cy = W // 2, H // 2
    # Draw elliptical ring from side: appears as a thick ellipse
    cv2.ellipse(img, (cx + 4, cy + 4), (160, 90), 0, 0, 360, shd, 32)
    cv2.ellipse(img, (cx, cy), (160, 90), 0, 0, 360, col, 28)
    # Highlight arc
    for deg in range(210, 330, 15):
        a = math.radians(deg)
        hx = int(cx + 148 * math.cos(a))
        hy = int(cy + 78 * math.sin(a))
        cv2.circle(img, (hx, hy), 3, (255, 255, 210), -1)
    img = _stamp(img, "side view", 10, H - 14)
    return img


# ── Chain ─────────────────────────────────────────────────────────────────────

def make_chain_top(karat: int = 22) -> np.ndarray:
    """Chain laid flat — top view."""
    import cv2
    img = _canvas()
    H, W = img.shape[:2]
    col = _gold_bgr(karat, noise=0.15)
    shd = _shadow(col)
    cx = W // 2
    link_h, link_w, gap = 26, 14, 3
    for i in range(12):
        cy = 60 + i * (link_h + gap)
        angle = 0 if i % 2 == 0 else 90
        cv2.ellipse(img, (cx + 2, cy + 2), (link_w, link_h // 2), angle, 0, 360, shd, 3)
        cv2.ellipse(img, (cx, cy), (link_w, link_h // 2), angle, 0, 360, col, 4)
        if i % 2 == 0:
            img = _specular(img, cx - link_w // 3, cy - link_h // 4, r=4)
    img = _stamp(img, "BIS 916" if karat == 22 else "BIS 750", 10, H - 14)
    return img


def make_chain_side(karat: int = 22) -> np.ndarray:
    """Chain hanging loosely — side view."""
    import cv2
    img = _canvas()
    H, W = img.shape[:2]
    col = _gold_bgr(karat, noise=0.12)
    shd = _shadow(col)
    # Draw a curved catenary chain
    for x in range(60, W - 60, 6):
        t = (x - W // 2) / (W // 2 - 60)
        y = int(H // 2 - 80 + 120 * t * t)
        cv2.circle(img, (x + 2, y + 2), 5, shd, -1)
        cv2.circle(img, (x, y), 5, col, -1)
        if x % 20 == 0:
            img = _specular(img, x - 2, y - 2, r=3)
    img = _stamp(img, "side view", 10, H - 14)
    return img


# ── Bangle ────────────────────────────────────────────────────────────────────

def make_bangle_top(karat: int = 22) -> np.ndarray:
    """Bangle — top view (wide circle)."""
    import cv2
    img = _canvas()
    H, W = img.shape[:2]
    col = _gold_bgr(karat, noise=0.08)
    shd = _shadow(col)
    cx, cy, outer_r, thick = W // 2, H // 2, 160, 24
    cv2.circle(img, (cx + 5, cy + 5), outer_r, shd, thick + 3)
    cv2.circle(img, (cx, cy), outer_r, col, thick)
    for deg in range(0, 360, 20):
        a = math.radians(deg)
        hx = int(cx + (outer_r - thick // 2) * math.cos(a))
        hy = int(cy + (outer_r - thick // 2) * math.sin(a))
        if deg % 40 == 0:
            cv2.circle(img, (hx, hy), 3, (255, 255, 210), -1)
    img = _stamp(img, "BIS 916", cx - 15, cy + 4)
    return img


def make_bangle_side(karat: int = 22) -> np.ndarray:
    """Bangle — side view showing band height."""
    import cv2
    img = _canvas()
    H, W = img.shape[:2]
    col = _gold_bgr(karat, noise=0.08)
    shd = _shadow(col)
    cx, cy = W // 2, H // 2
    # Wide flat ellipse (bangle on its side)
    cv2.ellipse(img, (cx + 5, cy + 5), (175, 40), 0, 0, 360, shd, 22)
    cv2.ellipse(img, (cx, cy), (175, 40), 0, 0, 360, col, 20)
    for deg in range(180, 360, 20):
        a = math.radians(deg)
        hx = int(cx + 163 * math.cos(a))
        hy = int(cy + 28 * math.sin(a))
        cv2.circle(img, (hx, hy), 3, (255, 255, 210), -1)
    img = _stamp(img, "side view", 10, H - 14)
    return img


# ── Earring ───────────────────────────────────────────────────────────────────

def make_earring_top(karat: int = 22) -> np.ndarray:
    """Stud earring — top view showing face."""
    import cv2
    img = _canvas()
    H, W = img.shape[:2]
    col = _gold_bgr(karat, noise=0.1)
    shd = _shadow(col)
    # Left earring
    cx1, cy = W // 2 - 80, H // 2
    cv2.circle(img, (cx1 + 3, cy + 3), 50, shd, -1)
    cv2.circle(img, (cx1, cy), 50, col, -1)
    cv2.circle(img, (cx1, cy), 50, shd, 4)
    img = _specular(img, cx1 - 15, cy - 15, r=10)
    # Right earring
    cx2 = W // 2 + 80
    cv2.circle(img, (cx2 + 3, cy + 3), 50, shd, -1)
    cv2.circle(img, (cx2, cy), 50, col, -1)
    cv2.circle(img, (cx2, cy), 50, shd, 4)
    img = _specular(img, cx2 - 15, cy - 15, r=10)
    # Centre gems (dark dots)
    cv2.circle(img, (cx1, cy), 12, (30, 30, 80), -1)
    cv2.circle(img, (cx2, cy), 12, (30, 30, 80), -1)
    img = _stamp(img, "BIS 916", W // 2 - 20, H - 14)
    return img


def make_earring_side(karat: int = 22) -> np.ndarray:
    """Hook earring — side profile."""
    import cv2
    img = _canvas()
    H, W = img.shape[:2]
    col = _gold_bgr(karat, noise=0.1)
    shd = _shadow(col)
    cx, cy = W // 2, H // 2
    # Hook arc
    cv2.ellipse(img, (cx + 2, cy - 40 + 2), (45, 60), 0, 180, 360, shd, 5)
    cv2.ellipse(img, (cx, cy - 40), (45, 60), 0, 180, 360, col, 4)
    # Drop pendant
    cv2.line(img, (cx, cy + 20 + 2), (cx, cy + 90 + 2), shd, 5)
    cv2.line(img, (cx, cy + 20), (cx, cy + 90), col, 4)
    cv2.circle(img, (cx + 2, cy + 100 + 2), 18, shd, -1)
    cv2.circle(img, (cx, cy + 100), 18, col, -1)
    img = _specular(img, cx - 6, cy + 90, r=5)
    img = _stamp(img, "side view", 10, H - 14)
    return img


# ── Pendant ───────────────────────────────────────────────────────────────────

def make_pendant_top(karat: int = 22) -> np.ndarray:
    """Heart/teardrop pendant — top view."""
    import cv2
    img = _canvas()
    H, W = img.shape[:2]
    col = _gold_bgr(karat, noise=0.1)
    shd = _shadow(col)
    cx, cy = W // 2, H // 2 + 20
    # Draw teardrop shape
    pts = []
    for deg in range(0, 361):
        a = math.radians(deg)
        r = 90 + 30 * math.cos(a)
        pts.append([int(cx + r * math.sin(a)), int(cy - r * math.cos(a) + 20)])
    pts_arr = np.array(pts, np.int32)
    cv2.fillPoly(img, [pts_arr + np.array([2, 2])], shd)
    cv2.fillPoly(img, [pts_arr], col)
    cv2.polylines(img, [pts_arr], True, shd, 3)
    # Bail (loop at top)
    cv2.ellipse(img, (cx + 2, cy - 90 + 2), (14, 10), 0, 0, 360, shd, 5)
    cv2.ellipse(img, (cx, cy - 90), (14, 10), 0, 0, 360, col, 4)
    img = _specular(img, cx - 25, cy - 10, r=12)
    img = _stamp(img, "BIS 916", cx - 20, H - 14)
    return img


def make_pendant_side(karat: int = 22) -> np.ndarray:
    """Pendant — side profile showing thickness."""
    import cv2
    img = _canvas()
    H, W = img.shape[:2]
    col = _gold_bgr(karat, noise=0.1)
    shd = _shadow(col)
    cx, cy = W // 2, H // 2
    # Thin oval from side
    cv2.ellipse(img, (cx + 3, cy + 3), (70, 110), 0, 0, 360, shd, 14)
    cv2.ellipse(img, (cx, cy), (70, 110), 0, 0, 360, col, 12)
    # Bail
    cv2.ellipse(img, (cx + 2, cy - 115 + 2), (12, 8), 0, 0, 360, shd, 5)
    cv2.ellipse(img, (cx, cy - 115), (12, 8), 0, 0, 360, col, 4)
    for deg in range(200, 340, 20):
        a = math.radians(deg)
        hx = int(cx + 62 * math.cos(a))
        hy = int(cy + 100 * math.sin(a))
        cv2.circle(img, (hx, hy), 3, (255, 255, 210), -1)
    img = _stamp(img, "side view", 10, H - 14)
    return img


# ── Coin ──────────────────────────────────────────────────────────────────────

def make_coin_top(karat: int = 24) -> np.ndarray:
    import cv2
    img = _canvas()
    H, W = img.shape[:2]
    col = _gold_bgr(karat, noise=0.05)
    shd = _shadow(col, factor=60)
    cx, cy, cr = W // 2, H // 2, 120
    cv2.circle(img, (cx + 5, cy + 5), cr, shd, -1)
    cv2.circle(img, (cx, cy), cr, col, -1)
    cv2.circle(img, (cx, cy), cr, shd, 4)
    for deg in range(210, 320, 10):
        a = math.radians(deg)
        cv2.circle(img, (int(cx + (cr - 10) * math.cos(a)), int(cy + (cr - 10) * math.sin(a))), 3, (255, 255, 210), -1)
    cv2.putText(img, "999.9", (cx - 28, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, shd, 1, cv2.LINE_AA)
    cv2.putText(img, "24K", (cx - 14, cy + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.38, shd, 1, cv2.LINE_AA)
    # Scale marker
    mx, my, ms = W - 80, H - 80, 50
    cv2.rectangle(img, (mx, my), (mx + ms, my + ms), (0, 0, 0), 2)
    cv2.rectangle(img, (mx + 5, my + 5), (mx + ms // 2, my + ms // 2), (0, 0, 0), -1)
    img = _stamp(img, "1cm", mx, my + ms + 14, scale=0.3)
    return img


def make_coin_side(karat: int = 24) -> np.ndarray:
    """Coin standing on edge — shows disc thickness."""
    import cv2
    img = _canvas()
    H, W = img.shape[:2]
    col = _gold_bgr(karat, noise=0.05)
    shd = _shadow(col, factor=60)
    cx, cy = W // 2, H // 2
    # Thin ellipse (coin on edge)
    cv2.ellipse(img, (cx + 4, cy + 4), (130, 20), 0, 0, 360, shd, -1)
    cv2.ellipse(img, (cx, cy), (130, 20), 0, 0, 360, col, -1)
    cv2.ellipse(img, (cx, cy), (130, 20), 0, 0, 360, shd, 3)
    for deg in range(180, 360, 15):
        a = math.radians(deg)
        hx = int(cx + 118 * math.cos(a))
        hy = int(cy + 15 * math.sin(a))
        cv2.circle(img, (hx, hy), 2, (255, 255, 210), -1)
    img = _stamp(img, "side view", 10, H - 14)
    return img


# ── Hallmark close-up ─────────────────────────────────────────────────────────

def make_hallmark_crop(purity: str = "916") -> np.ndarray:
    import cv2
    H, W = 320, 640
    img = np.full((H, W, 3), 205, dtype=np.uint8)

    # BIS triangle
    pts = np.array([[70, H - 50], [110, 40], [150, H - 50]], np.int32)
    cv2.fillPoly(img, [pts], (40, 40, 40))
    cv2.circle(img, (110, H // 2 + 20), 10, (205, 205, 205), -1)

    # Purity mark (large)
    cv2.putText(img, purity, (185, H // 2 + 20), cv2.FONT_HERSHEY_SIMPLEX, 2.2, (30, 30, 30), 3, cv2.LINE_AA)

    # Assay office mark
    cv2.putText(img, "AA", (350, H // 2 + 20), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (50, 50, 50), 2, cv2.LINE_AA)

    # HUID
    huid = "AB1C2D" if purity == "916" else "EF3G4H"
    cv2.putText(img, huid, (185, H // 2 + 70), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (55, 55, 55), 1, cv2.LINE_AA)

    # Year mark
    cv2.putText(img, "24", (430, H // 2 + 20), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (60, 60, 60), 2, cv2.LINE_AA)

    # BIS label
    cv2.putText(img, "BIS", (78, H // 2 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (190, 190, 190), 1, cv2.LINE_AA)

    # Border
    cv2.rectangle(img, (10, 10), (W - 10, H - 10), (100, 100, 100), 2)
    return img


# ── Generate all images ───────────────────────────────────────────────────────

print("Generating demo images…")

ITEMS: dict[str, tuple[np.ndarray, np.ndarray]] = {
    "ring":    (make_ring_top(22),    make_ring_side(22)),
    "chain":   (make_chain_top(22),   make_chain_side(22)),
    "bangle":  (make_bangle_top(22),  make_bangle_side(22)),
    "earring": (make_earring_top(22), make_earring_side(22)),
    "pendant": (make_pendant_top(22), make_pendant_side(22)),
    "coin":    (make_coin_top(24),    make_coin_side(24)),
}

for item_name, (top_img, side_img) in ITEMS.items():
    _save_jpg(top_img,  IMG_DIR / f"{item_name}_top.jpg")
    _save_jpg(side_img, IMG_DIR / f"{item_name}_side.jpg")

_save_jpg(make_hallmark_crop("916"), IMG_DIR / "hallmark_916.jpg")
_save_jpg(make_hallmark_crop("750"), IMG_DIR / "hallmark_750.jpg")

# Keep legacy names for backwards compatibility
import shutil
shutil.copy(IMG_DIR / "chain_top.jpg",  IMG_DIR / "gold_chain_22k.jpg")
shutil.copy(IMG_DIR / "ring_top.jpg",   IMG_DIR / "gold_ring_18k.jpg")
shutil.copy(IMG_DIR / "bangle_top.jpg", IMG_DIR / "gold_bangle_plated.jpg")
shutil.copy(IMG_DIR / "coin_top.jpg",   IMG_DIR / "gold_coin_24k.jpg")

# ── Audio generation ──────────────────────────────────────────────────────────

SR = 16_000

def _write_wav(samples: np.ndarray, path: Path) -> None:
    import struct
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())
    peak_db = 20 * math.log10(max(np.abs(pcm).max() / 32767, 1e-9))
    print(f"  saved {path} ({len(samples)/SR:.1f}s, peak {peak_db:.0f} dB)")


def _tap(f0: float, decay_ms: float, duration_s: float = 3.0,
         tap_at_s: float = 0.3, harmonics: int = 6) -> np.ndarray:
    n = int(duration_s * SR)
    out = np.zeros(n)
    tap_start = int(tap_at_s * SR)
    t = np.arange(n - tap_start) / SR
    tau = decay_ms / 1000.0
    envelope = np.exp(-t / tau)
    for k in range(1, harmonics + 1):
        freq = f0 * k
        if freq > SR / 2:
            break
        out[tap_start:] += (1.0 / k) * 0.7 * np.sin(2 * math.pi * freq * t) * envelope
    out += rng.normal(0, 0.003, n)
    peak = np.abs(out).max()
    if peak > 0:
        out = out / peak * 10 ** (-12 / 20)
    return out.astype(np.float32)


print("\nGenerating demo audio…")
_write_wav(_tap(f0=3200, decay_ms=310, tap_at_s=0.4), AUD_DIR / "tap_solid_22k.wav")
_write_wav(_tap(f0=1100, decay_ms=75,  tap_at_s=0.4), AUD_DIR / "tap_hollow_bangle.wav")
_write_wav(_tap(f0=3800, decay_ms=130, tap_at_s=0.4), AUD_DIR / "tap_plated.wav")
_write_wav(_tap(f0=2800, decay_ms=270, tap_at_s=0.4), AUD_DIR / "tap_solid_18k.wav")

print(f"\nDone. All assets in {OUT_DIR.resolve()}/")
