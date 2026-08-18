"""Écriture des fichiers générés (Excel/CSV/PDF) vers MinIO et génération
d'URLs pré-signées à expiration. Le bucket `artifacts` est provisionné par
docker-compose (Phase 0)."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from minio import Minio

from config.settings import get_settings

DEFAULT_EXPIRY = timedelta(hours=24)


@dataclass(frozen=True)
class UploadedArtifact:
    object_name: str
    url: str


def get_minio_client() -> Minio:
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def upload_artifact(
    path: Path,
    object_name: str | None = None,
    *,
    client: Minio | None = None,
    expiry: timedelta = DEFAULT_EXPIRY,
) -> UploadedArtifact:
    settings = get_settings()
    client = client or get_minio_client()
    object_name = object_name or path.name

    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    client.fput_object(
        settings.minio_bucket_artifacts, object_name, str(path), content_type=content_type
    )
    url = client.presigned_get_object(
        settings.minio_bucket_artifacts, object_name, expires=expiry
    )
    return UploadedArtifact(object_name=object_name, url=url)
