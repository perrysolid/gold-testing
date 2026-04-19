"""NFR-8: Deterministic config loaded once at startup via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Auth
    jwt_secret: str = Field(default="dev-secret-change-in-prod-32chars!!")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    otp_dev_bypass: str = "123456"

    # Gemini (FR-9.2)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_mock: bool = False

    # Gold price (FR-11.1)
    gold_api_provider: str = "mock"
    goldapi_key: str = ""
    metalpriceapi_key: str = ""
    gold_price_cache_ttl_seconds: int = 900
    gold_price_mock_inr_per_g_22k: float = 6900.0

    # LTV tiers — RBI 2025 (FR-7.5)
    ltv_small_ticket_max_inr: float = 250_000.0
    ltv_small_ticket: float = 0.85
    ltv_default: float = 0.75

    # Storage (FR-2.5)
    object_store: str = "local"
    local_storage_path: str = "./data/artifacts"
    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "aurum-assets"

    # Database
    db_url: str = "sqlite+aiosqlite:///./data/aurum.db"

    # Telemetry (NFR-12)
    log_level: str = "INFO"
    metrics_enabled: bool = True

    # Demo
    demo_lender_mode: bool = True

    # Model paths (NFR-15)
    jewelry_cls_model: str = "models/jewelry_cls_yolov8n.pt"
    hallmark_detector_model: str = "models/hallmark_yolov8n.pt"
    sam2_config: str = "models/sam2_hiera_tiny.yaml"
    sam2_checkpoint: str = "models/sam2_hiera_tiny.pt"
    midas_model_type: str = "MiDaS_small"
    weight_model: str = "models/weight_lgbm.pkl"
    purity_model: str = "models/purity_rf.pkl"
    audio_clf_model: str = "models/audio_clf.pkl"
    clip_model: str = "openai/clip-vit-base-patch32"


@lru_cache
def get_settings() -> Settings:
    return Settings()
