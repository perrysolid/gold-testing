# Aurum — Architecture

See IMPLEMENTATION_PLAN.md §5 for full system design.

## Services

| Service | Port | Purpose |
|---------|------|---------|
| `web` | 5173 | React + Vite PWA |
| `api` | 8000 | FastAPI backend (auth, assess, fusion, decision) |
| `minio` | 9000/9001 | S3-compatible object store for images/audio |
| `postgres` | 5432 | Production DB (SQLite used in dev) |

## Pipeline stages (§5.2)

```
Client (PWA)
  └─ POST /assess/start    → assessment_id + upload URLs
  └─ PUT images + audio   → MinIO / local
  └─ POST /assess/submit  → triggers BackgroundTasks

BackgroundTasks (in-process)
  ├─ Vision: classify → segment → scale → hallmark OCR → plating → depth
  └─ Audio: onset → features → classify

Fusion engine
  └─ Weighted evidence combination → FusionResult

Decision engine
  └─ YAML rules → PRE_APPROVE / NEEDS_VERIFICATION / REJECT
  └─ RBI LTV calc → max_loan_inr

Gemini 2.5 Flash
  └─ OCR fallback (if PaddleOCR conf < 0.6)
  └─ Explanation bullets
```
