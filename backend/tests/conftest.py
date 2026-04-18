"""Shared pytest fixtures. All external services mocked (NFR-8 / §22.4)."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Force mock mode before any imports load config
os.environ.setdefault("GEMINI_MOCK", "true")
os.environ.setdefault("GOLD_API_PROVIDER", "mock")
os.environ.setdefault("OBJECT_STORE", "local")
os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///./data/test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-32-chars-long!")
os.environ.setdefault("LOCAL_STORAGE_PATH", "./data/test_artifacts")


@pytest.fixture(scope="session")
def client() -> TestClient:
    from app.main import app
    return TestClient(app)
