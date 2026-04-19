"""Generate synthetic fixture images for vision integration tests.

Run once:  python tests/fixtures/generate.py
Outputs:
  gold_ring.jpg       — bright gold-coloured ring on white bg
  aruco_ring.jpg      — ring with ArUco DICT_5X5_50 marker id=0
  hallmark_crop.jpg   — close-up with "916 BIS ABCD12" text
  dark_image.jpg      — too-dark image (quality fail)
"""
from pathlib import Path
import numpy as np
import cv2

OUT = Path(__file__).parent


def _save(name: str, img: np.ndarray) -> None:
    cv2.imwrite(str(OUT / name), img)
    print(f"written {name} {img.shape}")


def make_gold_ring(size: int = 480) -> np.ndarray:
    """Bright gold-coloured ring on white background."""
    img = np.ones((size, size, 3), dtype=np.uint8) * 245  # near-white bg
    cx, cy, r_outer, r_inner = size // 2, size // 2, size // 3, size // 5
    # gold colour in BGR: #D4AF37 → (55, 175, 212)
    gold_bgr = (55, 175, 212)
    cv2.circle(img, (cx, cy), r_outer, gold_bgr, -1)
    cv2.circle(img, (cx, cy), r_inner, (245, 245, 245), -1)
    # add slight sheen
    for i in range(3):
        cv2.circle(img, (cx - r_outer // 4, cy - r_outer // 4), r_outer // 8,
                   (80, 200, 230), 2 + i)
    return img


def make_aruco_ring(size: int = 640) -> np.ndarray:
    """Gold ring with ArUco marker id=0 (DICT_5X5_50) in corner for scale."""
    img = make_gold_ring(size)
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50)
    marker_size = 60
    marker_img = cv2.aruco.generateImageMarker(aruco_dict, 0, marker_size)
    # embed in top-left corner
    img[10:10 + marker_size, 10:10 + marker_size] = cv2.cvtColor(
        marker_img, cv2.COLOR_GRAY2BGR
    )
    return img


def make_hallmark_crop(w: int = 320, h: int = 160) -> np.ndarray:
    """White crop with stamped hallmark text: 916 BIS ABCD12."""
    img = np.ones((h, w, 3), dtype=np.uint8) * 240
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, "916", (20, 60), font, 1.6, (30, 30, 30), 3)
    cv2.putText(img, "BIS", (140, 60), font, 1.2, (30, 30, 30), 2)
    cv2.putText(img, "ABCD12", (20, 130), font, 1.0, (50, 50, 50), 2)
    # simulate hallmark stamp border
    cv2.rectangle(img, (10, 10), (w - 10, h - 10), (80, 80, 80), 2)
    return img


def make_dark_image(size: int = 480) -> np.ndarray:
    """Under-exposed image — should fail brightness check."""
    img = np.zeros((size, size, 3), dtype=np.uint8)
    # dim circle so it's not pure black
    cv2.circle(img, (size // 2, size // 2), size // 3, (15, 12, 10), -1)
    return img


if __name__ == "__main__":
    _save("gold_ring.jpg", make_gold_ring())
    _save("aruco_ring.jpg", make_aruco_ring())
    _save("hallmark_crop.jpg", make_hallmark_crop())
    _save("dark_image.jpg", make_dark_image())
    print("done")
