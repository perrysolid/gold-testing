"""Train LightGBM weight-band regressor on synthetic physics data.

Physics model:  weight = volume × density(karat)
Features:       mask_area_px, thickness_mm, density, karat_idx
Target:         band_factor — the ±% uncertainty (0.10–0.45)

Band factor is narrower when:
  - area is large (more pixels = better estimate)
  - thickness is in a known range for item type
  - scale reference was detected (ppm reliable)

Run: python scripts/train_weight_model.py
Output: models/weight_lgbm.pkl
"""
import os
import pickle
import numpy as np

DENSITY: dict[int, float] = {24: 19.32, 22: 17.7, 18: 15.5, 14: 13.0}
KARAT_LIST = list(DENSITY.keys())

N = 4000
rng = np.random.default_rng(42)

# Generate synthetic feature vectors
karat_idx = rng.integers(0, len(KARAT_LIST), N)
karat = np.array([KARAT_LIST[i] for i in karat_idx])
density = np.array([DENSITY[k] for k in karat])

# mask_area_px: 10k–500k pixels (real jewellery range on 1600px image)
area_px = rng.uniform(10_000, 500_000, N)

# thickness_mm: 1–8 mm
thickness_mm = rng.uniform(1.0, 8.0, N)

# scale_conf: 0.3–1.0 (affects uncertainty)
scale_conf = rng.uniform(0.3, 1.0, N)

# Ground truth band_factor:
# High area + reliable scale + known karat → tight band
# Uncertainty comes from:
#   - low area (noisy mask)
#   - low scale_conf (no reference)
#   - extreme thickness (reflective/hollow)
area_norm = np.clip((area_px - 10_000) / 490_000, 0, 1)
thickness_norm = 1.0 - np.abs(thickness_mm - 3.5) / 4.5  # peaks at 3.5mm
band_factor = (
    0.30
    - 0.15 * area_norm
    - 0.08 * thickness_norm
    - 0.07 * (scale_conf - 0.3) / 0.7
    + rng.normal(0, 0.02, N)  # measurement noise
)
band_factor = np.clip(band_factor, 0.10, 0.45)

X = np.column_stack([area_px, thickness_mm, density, karat_idx.astype(float)])
y = band_factor

# Train/test split
split = int(N * 0.8)
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]

import lightgbm as lgb  # type: ignore[import]

params = {
    "objective": "regression",
    "metric": "mae",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "max_depth": 5,
    "min_data_in_leaf": 20,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "feature_fraction": 0.8,
    "seed": 42,
    "verbosity": -1,
    "num_threads": 1,
}

dtrain = lgb.Dataset(X_train, label=y_train)
dval = lgb.Dataset(X_test, label=y_test, reference=dtrain)
booster = lgb.train(
    params,
    dtrain,
    num_boost_round=200,
    valid_sets=[dval],
    callbacks=[lgb.early_stopping(20, verbose=False), lgb.log_evaluation(period=-1)],
)

y_pred = booster.predict(X_test)
mae = float(np.mean(np.abs(y_pred - y_test)))
print(f"Test MAE (band_factor): {mae:.4f}")
assert mae < 0.05, f"MAE too high: {mae}"

os.makedirs("models", exist_ok=True)
with open("models/weight_lgbm.pkl", "wb") as f:
    pickle.dump(booster, f)

print("Saved: models/weight_lgbm.pkl")
importances = booster.feature_importance(importance_type="gain")
print(f"Feature importances (gain): {dict(zip(['area_px','thickness_mm','density','karat_idx'], importances))}")
