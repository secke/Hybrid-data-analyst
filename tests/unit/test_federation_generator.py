from __future__ import annotations

from unittest.mock import MagicMock

from agent.federation.generator import (
    build_schema_context,
    build_user_message,
    generate_federated_sql,
)
from agent.schema.introspect import ColumnInfo, TableSchema

TABLES = [
    TableSchema(name="orders", columns=[ColumnInfo("order_id", "smallint", False)]),
    TableSchema(name="online_retail", columns=[ColumnInfo("country", "varchar", True)]),
]


def test_build_schema_context_includes_all_tables() -> None:
    context = build_schema_context(TABLES)
    assert "Table: orders" in context
    assert "Table: online_retail" in context


def test_build_schema_context_appends_extra_context() -> None:
    context = build_schema_context(TABLES, extra_context="1 GBP = 1.36 USD")
    assert "1 GBP = 1.36 USD" in context
    assert "Contexte supplémentaire" in context


def test_build_schema_context_omits_extra_section_when_empty() -> None:
    context = build_schema_context(TABLES)
    assert "Contexte supplémentaire" not in context


def test_build_user_message_includes_previous_error() -> None:
    message = build_user_message(
        "q", "schema", previous_sql="SELECT * FROM secret", previous_error="Table inconnue"
    )
    assert "SELECT * FROM secret" in message
    assert "Table inconnue" in message


def test_generate_federated_sql_calls_bedrock_and_extracts_sql() -> None:
    fake_client = MagicMock()
    fake_client.converse.return_value = MagicMock(text="```sql\nSELECT * FROM orders\n```")

    sql = generate_federated_sql("q", "schema context", fake_client)

    assert sql == "SELECT * FROM orders"
    fake_client.converse.assert_called_once()
    _, kwargs = fake_client.converse.call_args
    assert "DuckDB" in kwargs["system"]
    assert "normalize_country" in kwargs["system"]
