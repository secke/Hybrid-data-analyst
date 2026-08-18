"""Teste la fédération DuckDB contre le vrai Postgres local et le vrai
Parquet Online Retail II (docker-compose + ingestion Phase 0). Aucun appel
LLM."""

from __future__ import annotations

import pytest

from agent.federation.duckdb_conn import get_federated_connection
from agent.federation.executor import execute_federated
from agent.federation.introspect import introspect_federated_schema
from agent.schema.introspect import build_allowlist
from agent.sql.validator import validate_sql


@pytest.fixture
def federated_con():  # type: ignore[no-untyped-def]
    con = get_federated_connection()
    yield con
    con.close()


def test_federated_connection_exposes_northwind_tables(federated_con) -> None:  # type: ignore[no-untyped-def]
    assert federated_con.execute("SELECT count(*) FROM orders").fetchone()[0] == 830


def test_federated_connection_exposes_online_retail(federated_con) -> None:  # type: ignore[no-untyped-def]
    count = federated_con.execute("SELECT count(*) FROM online_retail").fetchone()[0]
    assert count > 1_000_000


def test_normalize_country_udf_is_registered(federated_con) -> None:  # type: ignore[no-untyped-def]
    row = federated_con.execute("SELECT normalize_country('UK')").fetchone()
    assert row[0] == "United Kingdom"


def test_cross_source_union_with_entity_resolution(federated_con) -> None:  # type: ignore[no-untyped-def]
    rows = federated_con.execute(
        """
        SELECT normalize_country(ship_country) AS country, COUNT(*) AS n
        FROM orders WHERE ship_country = 'UK'
        GROUP BY 1
        UNION ALL
        SELECT normalize_country(country) AS country, COUNT(*) AS n
        FROM online_retail WHERE country = 'United Kingdom'
        GROUP BY 1
        """
    ).fetchall()
    countries = {r[0] for r in rows}
    assert countries == {"United Kingdom"}
    assert len(rows) == 2


def test_introspect_federated_schema_includes_both_sources(federated_con) -> None:  # type: ignore[no-untyped-def]
    tables = introspect_federated_schema(federated_con)
    names = {t.name for t in tables}
    assert "orders" in names
    assert "online_retail" in names


def test_introspect_federated_schema_captures_columns(federated_con) -> None:  # type: ignore[no-untyped-def]
    tables = introspect_federated_schema(federated_con)
    online_retail = next(t for t in tables if t.name == "online_retail")
    assert "country" in online_retail.column_names
    assert "price" in online_retail.column_names


def test_execute_federated_returns_rows(federated_con) -> None:  # type: ignore[no-untyped-def]
    result = execute_federated(federated_con, "SELECT 1 AS x")
    assert result.ok
    assert result.rows == [{"x": 1}]


def test_execute_federated_captures_error(federated_con) -> None:  # type: ignore[no-untyped-def]
    result = execute_federated(federated_con, "SELECT * FROM nonexistent_table")
    assert not result.ok
    assert result.error is not None


def test_validate_sql_duckdb_accepts_union(federated_con) -> None:  # type: ignore[no-untyped-def]
    allowlist = build_allowlist(introspect_federated_schema(federated_con))
    sql = (
        "SELECT normalize_country(ship_country) AS country FROM orders "
        "UNION ALL "
        "SELECT normalize_country(country) AS country FROM online_retail"
    )
    result = validate_sql(sql, allowlist, dialect="duckdb")
    assert result.ok, result.reason
    executed = execute_federated(federated_con, result.sql)
    assert executed.ok


def test_validate_sql_duckdb_rejects_unknown_table(federated_con) -> None:  # type: ignore[no-untyped-def]
    allowlist = build_allowlist(introspect_federated_schema(federated_con))
    result = validate_sql("SELECT * FROM secret_table", allowlist, dialect="duckdb")
    assert not result.ok


def test_validate_sql_duckdb_rejects_ddl(federated_con) -> None:  # type: ignore[no-untyped-def]
    allowlist = build_allowlist(introspect_federated_schema(federated_con))
    result = validate_sql("DROP TABLE orders", allowlist, dialect="duckdb")
    assert not result.ok
