from __future__ import annotations

from unittest.mock import MagicMock

from agent.sql.generator import _extract_sql, build_user_message, generate_sql


def test_extract_sql_from_fenced_block() -> None:
    text = "Voici la requête:\n```sql\nSELECT 1\n```\nFin."
    assert _extract_sql(text) == "SELECT 1"


def test_extract_sql_from_fenced_block_without_language_tag() -> None:
    text = "```\nSELECT 1\n```"
    assert _extract_sql(text) == "SELECT 1"


def test_extract_sql_falls_back_to_raw_text_without_fence() -> None:
    text = "  SELECT 1  "
    assert _extract_sql(text) == "SELECT 1"


def test_build_user_message_includes_schema_and_question() -> None:
    message = build_user_message("Combien de clients ?", "Table: customers")
    assert "Table: customers" in message
    assert "Combien de clients ?" in message


def test_build_user_message_includes_previous_error_when_retrying() -> None:
    message = build_user_message(
        "Combien de clients ?",
        "Table: customers",
        previous_sql="SELECT * FROM secret",
        previous_error="Table inconnue: secret",
    )
    assert "SELECT * FROM secret" in message
    assert "Table inconnue: secret" in message


def test_build_user_message_omits_retry_section_on_first_attempt() -> None:
    message = build_user_message("Combien de clients ?", "Table: customers")
    assert "précédente tentative" not in message


def test_generate_sql_calls_bedrock_and_extracts_sql() -> None:
    fake_client = MagicMock()
    fake_client.converse.return_value = MagicMock(
        text="```sql\nSELECT count(*) FROM customers\n```"
    )

    sql = generate_sql("Combien de clients ?", "Table: customers", fake_client)

    assert sql == "SELECT count(*) FROM customers"
    fake_client.converse.assert_called_once()
    _, kwargs = fake_client.converse.call_args
    assert "SELECT" in kwargs["system"] or "Tu es un expert PostgreSQL" in kwargs["system"]
