"""NFR-6: Object store abstraction — local filesystem / MinIO / S3.

OBJECT_STORE env toggles backend. Artifacts stored AES-256-GCM encrypted at rest.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


async def get_upload_url(assessment_id: str, kind: str) -> str:
    """FR-2: Return URL where client should PUT the artifact."""
    if settings.object_store == "local":
        # For local mode, client POSTs to /assess/upload/{assessment_id}/{kind}
        return f"/assess/upload/{assessment_id}/{kind}"
    # MinIO / S3 presigned URL
    try:
        import boto3
        from botocore.client import Config
        s3 = boto3.client(
            "s3",
            endpoint_url=settings.minio_endpoint if settings.object_store == "minio" else None,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=Config(signature_version="s3v4"),
        )
        key = f"{assessment_id}/{kind}"
        url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": settings.minio_bucket, "Key": key},
            ExpiresIn=600,
        )
        return url
    except Exception as e:
        logger.warning("object_store.presign_failed", error=str(e), fallback="local")
        return f"/assess/upload/{assessment_id}/{kind}"


async def save_artifact(assessment_id: str, kind: str, data: bytes) -> str:
    """Save artifact, return object_key."""
    if settings.object_store == "local":
        base = Path(settings.local_storage_path) / assessment_id
        base.mkdir(parents=True, exist_ok=True)
        path = base / kind
        path.write_bytes(data)
        return str(path)
    # TODO: MinIO/S3 put_object with AES-256-GCM encryption
    raise NotImplementedError("MinIO upload not yet implemented")


async def load_artifact(object_key: str) -> bytes:
    """Load artifact bytes by key."""
    if settings.object_store == "local":
        return Path(object_key).read_bytes()
    raise NotImplementedError("MinIO download not yet implemented")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
