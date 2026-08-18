"""Teste l'upload MinIO et les URLs pré-signées contre le vrai MinIO local
(docker-compose). Aucun appel LLM."""

from __future__ import annotations

import uuid

import pytest
import requests

from agent.export.storage import get_minio_client, upload_artifact
from config.settings import get_settings


def _minio_available() -> bool:
    try:
        client = get_minio_client()
        return client.bucket_exists(get_settings().minio_bucket_artifacts)
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _minio_available(), reason="MinIO n'est pas disponible")


@pytest.fixture
def cleanup_minio():  # type: ignore[no-untyped-def]
    created: list[str] = []
    yield created
    client = get_minio_client()
    settings = get_settings()
    for object_name in created:
        client.remove_object(settings.minio_bucket_artifacts, object_name)


def test_upload_artifact_is_downloadable_via_presigned_url(tmp_path, cleanup_minio) -> None:  # type: ignore[no-untyped-def]
    local_path = tmp_path / "test.csv"
    local_path.write_text("a,b\n1,2\n", encoding="utf-8")
    object_name = f"pytest/{uuid.uuid4().hex}.csv"
    cleanup_minio.append(object_name)

    uploaded = upload_artifact(local_path, object_name=object_name)

    assert uploaded.object_name == object_name
    response = requests.get(uploaded.url, timeout=10)
    assert response.status_code == 200
    assert response.text == "a,b\n1,2\n"


def test_upload_artifact_sets_correct_content_type(tmp_path, cleanup_minio) -> None:  # type: ignore[no-untyped-def]
    local_path = tmp_path / "report.pdf"
    local_path.write_bytes(b"%PDF-1.7 fake content")
    object_name = f"pytest/{uuid.uuid4().hex}.pdf"
    cleanup_minio.append(object_name)

    uploaded = upload_artifact(local_path, object_name=object_name)

    response = requests.get(uploaded.url, timeout=10)
    assert response.headers["Content-Type"] == "application/pdf"


def test_upload_artifact_defaults_object_name_to_filename(tmp_path, cleanup_minio) -> None:  # type: ignore[no-untyped-def]
    local_path = tmp_path / f"{uuid.uuid4().hex}.csv"
    local_path.write_text("x", encoding="utf-8")
    cleanup_minio.append(local_path.name)

    uploaded = upload_artifact(local_path)

    assert uploaded.object_name == local_path.name
