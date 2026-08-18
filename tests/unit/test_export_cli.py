"""Teste l'orchestration export_question (SQL mocké, écriture de fichiers et
upload MinIO réels)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.export import cli as export_cli
from agent.export.storage import get_minio_client
from agent.sql.pipeline import PipelineResult
from config.settings import get_settings

FAKE_RESULT = PipelineResult(
    question="CA par categorie",
    ok=True,
    sql="SELECT category, revenue FROM x",
    columns=["category", "revenue"],
    rows=[{"category": "Beverages", "revenue": 12000.5}, {"category": "Dairy", "revenue": 15300.0}],
    row_count=2,
)


def _minio_available() -> bool:
    try:
        client = get_minio_client()
        return client.bucket_exists(get_settings().minio_bucket_artifacts)
    except Exception:  # noqa: BLE001
        return False


def test_export_question_raises_when_sql_pipeline_fails(mocker) -> None:  # type: ignore[no-untyped-def]
    failed_result = PipelineResult(question="q", ok=False, sql=None)
    mocker.patch.object(export_cli, "ask_sql", return_value=failed_result)

    with pytest.raises(RuntimeError):
        export_cli.export_question("q", upload=False)


def test_export_question_writes_local_files_without_upload(mocker, tmp_path) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(export_cli, "ask_sql", return_value=FAKE_RESULT)
    mocker.patch.object(export_cli, "EXPORT_DIR", tmp_path)

    outputs = export_cli.export_question("CA par categorie ?", upload=False)

    assert set(outputs) == {"xlsx", "csv", "pdf"}
    for location in outputs.values():
        assert Path(location).exists()


def test_export_question_respects_formats_filter(mocker, tmp_path) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(export_cli, "ask_sql", return_value=FAKE_RESULT)
    mocker.patch.object(export_cli, "EXPORT_DIR", tmp_path)

    outputs = export_cli.export_question("CA par categorie ?", formats=("csv",), upload=False)

    assert set(outputs) == {"csv"}


@pytest.mark.skipif(not _minio_available(), reason="MinIO n'est pas disponible")
def test_export_question_uploads_and_files_are_downloadable(mocker, tmp_path) -> None:  # type: ignore[no-untyped-def]
    import requests

    mocker.patch.object(export_cli, "ask_sql", return_value=FAKE_RESULT)
    mocker.patch.object(export_cli, "EXPORT_DIR", tmp_path)

    outputs = export_cli.export_question(
        "CA par categorie ?", formats=("csv",), upload=True
    )

    try:
        response = requests.get(outputs["csv"], timeout=10)
        assert response.status_code == 200
        assert "Beverages" in response.text
    finally:
        client = get_minio_client()
        settings = get_settings()
        client.remove_object(settings.minio_bucket_artifacts, "ca-par-categorie.csv")
