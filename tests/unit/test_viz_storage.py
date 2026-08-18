from __future__ import annotations

from agent.viz.storage import save_chart


def test_save_chart_writes_png_and_html(tmp_path) -> None:  # type: ignore[no-untyped-def]
    png_bytes = b"\x89PNG\r\n\x1a\nfake"
    html = "<html>chart</html>"

    saved = save_chart(png_bytes, html, name="test-chart", directory=tmp_path)

    assert saved.png_path == tmp_path / "test-chart.png"
    assert saved.html_path == tmp_path / "test-chart.html"
    assert saved.png_path.read_bytes() == png_bytes
    assert saved.html_path.read_text(encoding="utf-8") == html


def test_save_chart_creates_directory(tmp_path) -> None:  # type: ignore[no-untyped-def]
    directory = tmp_path / "nested" / "charts"
    saved = save_chart(b"png", "html", name="chart", directory=directory)
    assert saved.png_path.exists()


def test_save_chart_generates_unique_name_when_not_given(tmp_path) -> None:  # type: ignore[no-untyped-def]
    saved1 = save_chart(b"png1", "html1", directory=tmp_path)
    saved2 = save_chart(b"png2", "html2", directory=tmp_path)
    assert saved1.png_path != saved2.png_path
