"""Teste l'orchestration build_report (SQL et Bedrock mockés, journal/PDF
réels)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import agent.report.cli as report_cli
from agent.audit.journal import verify_journal
from agent.sql.pipeline import PipelineResult

FAKE_SQL_RESULT = PipelineResult(
    question="CA par pays",
    ok=True,
    sql="SELECT country, count(*) AS n FROM online_retail GROUP BY country",
    columns=["country", "n"],
    rows=[{"country": "United Kingdom", "n": 981330}, {"country": "France", "n": 14330}],
    row_count=2,
)


def _fake_inner_bedrock() -> MagicMock:
    client = MagicMock()
    client.converse.return_value = MagicMock(
        text="# Analyse\n\nLe Royaume-Uni domine [Réf: index 0].",
        input_tokens=200,
        output_tokens=50,
        stop_reason="end_turn",
    )
    return client


def test_build_report_raises_when_sql_pipeline_fails(mocker) -> None:  # type: ignore[no-untyped-def]
    failed_result = PipelineResult(question="q", ok=False, sql=None)
    mocker.patch.object(report_cli, "ask_sql", return_value=failed_result)

    with pytest.raises(RuntimeError):
        report_cli.build_report("q", upload=False)


def test_build_report_creates_pdf_without_upload(mocker, tmp_path) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(report_cli, "ask_sql", return_value=FAKE_SQL_RESULT)
    mocker.patch.object(report_cli, "REPORT_DIR", tmp_path)
    mocker.patch(
        "agent.observability.traced_bedrock.BedrockClient", return_value=_fake_inner_bedrock()
    )

    pdf_path, url = report_cli.build_report("CA par pays ?", upload=False)

    assert pdf_path.exists()
    assert url is None


def test_build_report_pdf_content_matches_sql_result(mocker, tmp_path) -> None:  # type: ignore[no-untyped-def]
    import subprocess

    mocker.patch.object(report_cli, "ask_sql", return_value=FAKE_SQL_RESULT)
    mocker.patch.object(report_cli, "REPORT_DIR", tmp_path)
    mocker.patch(
        "agent.observability.traced_bedrock.BedrockClient", return_value=_fake_inner_bedrock()
    )

    pdf_path, _ = report_cli.build_report("CA par pays ?", upload=False)

    text = subprocess.run(["pdftotext", str(pdf_path), "-"], capture_output=True, text=True).stdout
    assert "United Kingdom" in text
    assert "981330" in text
    assert "Réf: index 0" in text


def test_journal_remains_verifiable_after_build_report(mocker, tmp_path) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(report_cli, "ask_sql", return_value=FAKE_SQL_RESULT)
    mocker.patch.object(report_cli, "REPORT_DIR", tmp_path)
    mocker.patch(
        "agent.observability.traced_bedrock.BedrockClient", return_value=_fake_inner_bedrock()
    )

    report_cli.build_report("CA par pays ?", upload=False)

    result = verify_journal()
    assert result.ok
