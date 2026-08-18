from __future__ import annotations

import pandas as pd

from agent.export.csv_export import write_csv


def test_write_csv_creates_readable_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    df = pd.DataFrame({"category": ["A", "B"], "revenue": [100, 200]})
    path = write_csv(tmp_path / "data.csv", df)

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "category,revenue" in content
    assert "A,100" in content
    assert "B,200" in content


def test_write_csv_creates_parent_directory(tmp_path) -> None:  # type: ignore[no-untyped-def]
    df = pd.DataFrame({"a": [1]})
    path = write_csv(tmp_path / "nested" / "data.csv", df)
    assert path.exists()


def test_write_csv_roundtrips_with_pandas(tmp_path) -> None:  # type: ignore[no-untyped-def]
    df = pd.DataFrame({"category": ["A", "B"], "revenue": [100.5, 200.25]})
    path = write_csv(tmp_path / "data.csv", df)
    reloaded = pd.read_csv(path)
    pd.testing.assert_frame_equal(df, reloaded)
