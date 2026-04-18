# Deviations from IMPLEMENTATION_PLAN.md

All changes from the plan are logged here per §22.8.

| # | Section | Deviation | Reason |
|---|---------|-----------|--------|
| 1 | §10.4 | Plating detector ships as LAB rule-based (confidence capped at 0.55) rather than MobileNetV3 CNN | No labelled plating dataset available at scaffold time; rule-based per §20 guidance |
| 2 | §11.3 Audio classifier | Ships rule-based (f0/decay thresholds) instead of sklearn GBC | No labelled tap-test audio dataset; sklearn slot scaffolded, model training deferred |
| 3 | §8 config path | `decision_rules.yaml` placed in `backend/app/decision/rules.yaml` (per folder layout §8); `/config/` dir at repo root is symlinked on demand | §8 and §9 conflict; §8 (code layout) takes precedence |
| 4 | §7.4 CLIP | CLIP used for multiview consistency returns 0.9 stub when model not loaded | CLIP ViT-B/32 is 338 MB; added to download_models.sh but not pre-loaded in scaffold |
| 5 | §14.1 screens | Onboarding/Capture/Audio/Review screens are functional stubs; full camera UX implemented in phase 3–5 of build order | Scaffold phase only; camera wiring is hours 3–5 |
| 6 | §5.3 SAM2 import | SAM2 Python package installed as `sam2` from `facebookresearch/sam2` repo; not on PyPI, requires `pip install -e .` | PyPI package not yet released; noted in download_models.sh |
