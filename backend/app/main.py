"""Aurum FastAPI application entry point.

NFR-12: Structured JSON logging + per-request IDs.
NFR-14: Single docker compose up starts this on port 8000.
"""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, make_asgi_app

from app.config import get_settings
from app.db.models import create_db_and_tables

logger = structlog.get_logger()

settings = get_settings()

REQUEST_COUNT = Counter(
    "aurum_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "aurum_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("aurum.startup", version="0.1.0", env=settings.object_store)
    await create_db_and_tables()
    yield
    logger.info("aurum.shutdown")


app = FastAPI(
    title="Aurum API",
    description="AI-powered remote gold assessment for NBFC lending",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — tighten in prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next: any) -> Response:  # type: ignore[valid-type]
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    with structlog.contextvars.bound_contextvars(request_id=request_id):
        response: Response = await call_next(request)
        elapsed = time.perf_counter() - start
        path = request.url.path
        REQUEST_COUNT.labels(request.method, path, response.status_code).inc()
        REQUEST_LATENCY.labels(request.method, path).observe(elapsed)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "http.request",
            method=request.method,
            path=path,
            status=response.status_code,
            duration_ms=round(elapsed * 1000, 1),
        )
    return response


# ── Health (NFR-2) ────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "aurum-api"}


# ── Prometheus metrics (NFR-12, US-C2) ───────────────────────────────────────
if settings.metrics_enabled:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


# ── Routers (added incrementally per build order §18) ────────────────────────
# Phase 1–3: auth + assess + services
from app.auth.routes import router as auth_router  # noqa: E402
from app.assess.routes import router as assess_router  # noqa: E402

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(assess_router, prefix="/assess", tags=["assess"])
