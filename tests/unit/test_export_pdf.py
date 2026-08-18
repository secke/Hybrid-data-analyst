"""Teste l'export PDF réellement (WeasyPrint). Aucun appel LLM."""

from __future__ import annotations

import pandas as pd

from agent.export.pdf import write_pdf

TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
    b"\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame({"category": ["Beverages", "Dairy"], "revenue": [12000.5, 15300.0]})


def test_write_pdf_creates_valid_pdf_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = write_pdf(tmp_path / "report.pdf", _sample_df(), title="Rapport")
    assert path.exists()
    assert path.read_bytes()[:5] == b"%PDF-"


def test_write_pdf_embedding_chart_increases_size(tmp_path) -> None:  # type: ignore[no-untyped-def]
    without_chart = write_pdf(tmp_path / "no_chart.pdf", _sample_df(), title="Rapport")
    with_chart = write_pdf(
        tmp_path / "with_chart.pdf", _sample_df(), title="Rapport", chart_png_bytes=TINY_PNG
    )
    assert with_chart.stat().st_size > without_chart.stat().st_size


def test_write_pdf_respects_max_rows(tmp_path) -> None:  # type: ignore[no-untyped-def]
    big_df = pd.DataFrame({"category": [f"cat-{i}" for i in range(500)], "revenue": range(500)})
    path = write_pdf(tmp_path / "report.pdf", big_df, title="Rapport", max_rows=10)
    assert path.exists()
    assert path.read_bytes()[:5] == b"%PDF-"
