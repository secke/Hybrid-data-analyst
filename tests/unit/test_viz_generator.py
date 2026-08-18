from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from agent.viz.generator import build_user_message, generate_chart_code


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame({"category": ["A", "B", "A"], "amount": [10, 20, 30]})


def test_build_user_message_includes_description_and_question() -> None:
    message = build_user_message("Graphique ?", "DataFrame `df` : 3 lignes.")
    assert "DataFrame `df`" in message
    assert "Graphique ?" in message


def test_build_user_message_includes_previous_error_when_retrying() -> None:
    message = build_user_message(
        "Graphique ?",
        "DataFrame `df` : 3 lignes.",
        previous_code="fig = px.bar(df, x='foo')",
        previous_error="KeyError: 'foo'",
    )
    assert "fig = px.bar(df, x='foo')" in message
    assert "KeyError: 'foo'" in message


def test_generate_chart_code_calls_bedrock_and_extracts_code() -> None:
    fake_client = MagicMock()
    fake_client.converse.return_value = MagicMock(
        text="```python\nfig = px.bar(df, x='category', y='amount')\n```"
    )

    code = generate_chart_code("Montants par catégorie ?", _sample_df(), fake_client)

    assert code == "fig = px.bar(df, x='category', y='amount')"
    fake_client.converse.assert_called_once()
    _, kwargs = fake_client.converse.call_args
    assert "Plotly" in kwargs["system"]
    assert "`fig`" in kwargs["system"]
