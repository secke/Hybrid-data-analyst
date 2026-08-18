from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from agent.python_exec.generator import build_user_message, describe_dataframe, generate_code


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame({"category": ["A", "B", "A"], "amount": [10, 20, 30]})


def test_describe_dataframe_includes_columns_and_types() -> None:
    description = describe_dataframe(_sample_df())
    assert "category" in description
    assert "amount" in description
    assert "3 lignes" in description


def test_describe_dataframe_includes_sample_rows() -> None:
    description = describe_dataframe(_sample_df(), sample_rows=2)
    assert "Aperçu" in description


def test_build_user_message_includes_description_and_question() -> None:
    message = build_user_message("Combien ?", "DataFrame `df` : 3 lignes.")
    assert "DataFrame `df`" in message
    assert "Combien ?" in message


def test_build_user_message_includes_previous_error_when_retrying() -> None:
    message = build_user_message(
        "Combien ?",
        "DataFrame `df` : 3 lignes.",
        previous_code="result = df.foo",
        previous_error="AttributeError: foo",
    )
    assert "result = df.foo" in message
    assert "AttributeError: foo" in message


def test_generate_code_calls_bedrock_and_extracts_code() -> None:
    fake_client = MagicMock()
    fake_client.converse.return_value = MagicMock(
        text="```python\nresult = df['amount'].sum()\n```"
    )

    code = generate_code("Somme des montants ?", _sample_df(), fake_client)

    assert code == "result = df['amount'].sum()"
    fake_client.converse.assert_called_once()
    _, kwargs = fake_client.converse.call_args
    assert "pandas" in kwargs["system"]
