from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from agent.federation.reviews_synthesis import (
    format_reviews_for_prompt,
    reviews_available,
    sample_reviews,
    synthesize_reviews,
)


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "label": ["positive", "negative"],
            "text": ["Great product, fast shipping!", "Terrible quality, broke immediately."],
        }
    )


def test_reviews_available_false_when_file_missing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert reviews_available(path=tmp_path / "nonexistent.parquet") is False


def test_reviews_available_true_when_file_exists(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "reviews.parquet"
    _sample_df().to_parquet(path)
    assert reviews_available(path=path) is True


def test_sample_reviews_raises_clear_error_when_missing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(FileNotFoundError, match="Kaggle"):
        sample_reviews(path=tmp_path / "nonexistent.parquet")


def test_sample_reviews_returns_requested_sample_size(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "reviews.parquet"
    _sample_df().to_parquet(path)
    sample = sample_reviews(n=1, path=path)
    assert len(sample) == 1


def test_sample_reviews_caps_at_available_rows(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "reviews.parquet"
    _sample_df().to_parquet(path)
    sample = sample_reviews(n=1000, path=path)
    assert len(sample) == 2


def test_format_reviews_for_prompt_includes_label_and_text() -> None:
    formatted = format_reviews_for_prompt(_sample_df())
    assert "positive" in formatted
    assert "Great product" in formatted
    assert "negative" in formatted


def test_format_reviews_truncates_long_text() -> None:
    df = pd.DataFrame({"label": ["positive"], "text": ["x" * 1000]})
    formatted = format_reviews_for_prompt(df, max_chars_per_review=50)
    assert len(formatted.splitlines()[0]) < 100


def test_synthesize_reviews_calls_bedrock_and_strips_response() -> None:
    fake_client = MagicMock()
    fake_client.converse.return_value = MagicMock(text="  Synthese generee.  ")

    synthesis = synthesize_reviews(_sample_df(), fake_client)

    assert synthesis == "Synthese generee."
    fake_client.converse.assert_called_once()
