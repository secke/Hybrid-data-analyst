from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from agent.report.generator import build_user_message, generate_narrative


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame({"country": ["United Kingdom", "France"], "n": [981330, 14330]})


def test_build_user_message_includes_question_and_data() -> None:
    message = build_user_message("Répartition par pays ?", "DataFrame `df`: 2 lignes.", None)
    assert "Répartition par pays ?" in message
    assert "DataFrame `df`" in message


def test_build_user_message_includes_sql_when_provided() -> None:
    message = build_user_message("q", "data", "SELECT * FROM t")
    assert "SELECT * FROM t" in message


def test_generate_narrative_calls_bedrock_and_strips_response() -> None:
    fake_client = MagicMock()
    fake_client.converse.return_value = MagicMock(
        text="  # Titre\n\nTexte [Réf: index 0].  "
    )

    narrative = generate_narrative("q", _sample_df(), fake_client, sql="SELECT ...")

    assert narrative == "# Titre\n\nTexte [Réf: index 0]."
    fake_client.converse.assert_called_once()


def test_generate_narrative_system_prompt_requires_references() -> None:
    fake_client = MagicMock()
    fake_client.converse.return_value = MagicMock(text="ok")

    generate_narrative("q", _sample_df(), fake_client)

    _, kwargs = fake_client.converse.call_args
    assert "Réf" in kwargs["system"]
    assert "index" in kwargs["system"]
