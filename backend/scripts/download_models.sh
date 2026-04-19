#!/usr/bin/env bash
# Download model weights into backend/models/
# Run from the backend/ directory: bash scripts/download_models.sh
set -euo pipefail

MODELS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/models"
mkdir -p "$MODELS_DIR"

echo "→ Downloading model weights to $MODELS_DIR"

# ── YOLOv8n base (AGPL-3.0 — cite Ultralytics) ───────────────────────────────
# Used as backbone for jewelry classifier; fine-tune with our dataset
if [ ! -f "$MODELS_DIR/yolov8n.pt" ]; then
    python3 -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
  mv ~/.config/Ultralytics/yolov8n.pt "$MODELS_DIR/" 2>/dev/null || \
    echo "  yolov8n.pt already in models/ or check ultralytics cache"
fi

# ── SAM2 Hiera Tiny (Apache 2.0 — Meta AI) ───────────────────────────────────
# https://github.com/facebookresearch/sam2
SAM2_CKPT="$MODELS_DIR/sam2_hiera_tiny.pt"
if [ ! -f "$SAM2_CKPT" ]; then
  echo "→ Downloading SAM2 tiny checkpoint (~155 MB)"
  curl -L -o "$SAM2_CKPT" \
    "https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_tiny.pt"
fi

# ── MiDaS small (MIT — Intel ISL) ────────────────────────────────────────────
# Loaded via torch.hub on first inference; no manual download needed.
# Run to pre-cache:
#   python -c "import torch; torch.hub.load('intel-isl/MiDaS','MiDaS_small',trust_repo=True)"

# ── Jewellery classifier (fine-tuned) — train with ml/notebooks/01_dataset_prep.ipynb
# After training, copy to models/jewelry_cls_yolov8n.pt

# ── Hallmark detector (fine-tuned) — train with ml/notebooks/02_train_hallmark_detector.ipynb
# After training, copy to models/hallmark_yolov8n.pt

echo "✓ Base model download complete. Fine-tuned weights must be trained separately."
echo "  See ml/notebooks/ for training instructions."
