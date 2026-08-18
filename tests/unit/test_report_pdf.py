"""Teste l'export PDF du rapport traçable réellement (WeasyPrint). Aucun
appel LLM."""

from __future__ import annotations

import pandas as pd

from agent.report.pdf import write_traceable_report_pdf


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame({"country": ["United Kingdom", "France"], "n": [981330, 14330]})


def test_write_traceable_report_pdf_creates_valid_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = write_traceable_report_pdf(
        tmp_path / "report.pdf",
        title="Rapport",
        narrative="# Titre\n\nTexte [Réf: index 0].",
        df=_sample_df(),
        trace_metadata={"identity": "pytest"},
    )
    assert path.exists()
    assert path.read_bytes()[:5] == b"%PDF-"


def test_write_traceable_report_pdf_includes_trace_metadata(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import subprocess

    path = write_traceable_report_pdf(
        tmp_path / "report.pdf",
        title="Rapport",
        narrative="Texte.",
        df=_sample_df(),
        sql="SELECT country, n FROM t",
        trace_metadata={"identity": "pytest-user", "model_id": "claude-sonnet-4-5"},
    )
    text = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True).stdout
    assert "pytest-user" in text
    assert "claude-sonnet-4-5" in text
    assert "SELECT country, n FROM t" in text


def test_write_traceable_report_pdf_includes_data_table(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import subprocess

    path = write_traceable_report_pdf(
        tmp_path / "report.pdf",
        title="Rapport",
        narrative="Texte.",
        df=_sample_df(),
        trace_metadata={},
    )
    text = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True).stdout
    assert "United Kingdom" in text
    assert "981330" in text


def test_write_traceable_report_pdf_embeds_chart_when_provided(tmp_path) -> None:  # type: ignore[no-untyped-def]
    tiny_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
        b"\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    without_chart = write_traceable_report_pdf(
        tmp_path / "no_chart.pdf", title="R", narrative="T", df=_sample_df(), trace_metadata={}
    )
    with_chart = write_traceable_report_pdf(
        tmp_path / "with_chart.pdf",
        title="R",
        narrative="T",
        df=_sample_df(),
        trace_metadata={},
        chart_png_bytes=tiny_png,
    )
    assert with_chart.stat().st_size > without_chart.stat().st_size
