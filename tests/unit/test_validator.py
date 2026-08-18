from __future__ import annotations

from agent.sql.validator import DEFAULT_MAX_LIMIT, validate_sql

ALLOWLIST = {
    "orders": {"order_id", "customer_id", "order_date", "freight", "ship_country"},
    "customers": {"customer_id", "company_name"},
}


def test_valid_select_gets_limit_injected() -> None:
    result = validate_sql("SELECT order_id FROM orders", ALLOWLIST)
    assert result.ok
    assert result.sql is not None
    assert f"LIMIT {DEFAULT_MAX_LIMIT}" in result.sql


def test_valid_select_with_limit_under_max_is_preserved() -> None:
    result = validate_sql("SELECT order_id FROM orders LIMIT 10", ALLOWLIST)
    assert result.ok
    assert result.sql is not None
    assert "LIMIT 10" in result.sql


def test_limit_over_max_is_capped() -> None:
    result = validate_sql("SELECT order_id FROM orders LIMIT 999999", ALLOWLIST, max_limit=1000)
    assert result.ok
    assert result.sql is not None
    assert "LIMIT 1000" in result.sql
    assert "999999" not in result.sql


def test_multi_statement_is_rejected() -> None:
    result = validate_sql("SELECT 1; DROP TABLE orders;", ALLOWLIST)
    assert not result.ok
    assert "seule instruction" in (result.reason or "").lower()


def test_drop_is_rejected() -> None:
    result = validate_sql("DROP TABLE orders", ALLOWLIST)
    assert not result.ok
    assert "SELECT" in (result.reason or "")


def test_update_is_rejected() -> None:
    result = validate_sql("UPDATE orders SET freight = 0", ALLOWLIST)
    assert not result.ok


def test_insert_is_rejected() -> None:
    result = validate_sql("INSERT INTO orders (order_id) VALUES (1)", ALLOWLIST)
    assert not result.ok


def test_unknown_table_is_rejected() -> None:
    result = validate_sql("SELECT * FROM secret_table", ALLOWLIST)
    assert not result.ok
    assert "secret_table" in (result.reason or "")


def test_unknown_column_is_rejected() -> None:
    result = validate_sql("SELECT nonexistent_col FROM orders", ALLOWLIST)
    assert not result.ok


def test_join_with_aliases_is_accepted() -> None:
    sql = (
        "SELECT o.order_id, c.company_name FROM orders o "
        "JOIN customers c ON o.customer_id = c.customer_id"
    )
    result = validate_sql(sql, ALLOWLIST)
    assert result.ok, result.reason


def test_empty_sql_is_rejected() -> None:
    result = validate_sql("   ", ALLOWLIST)
    assert not result.ok


def test_unparseable_sql_is_rejected() -> None:
    result = validate_sql("SELECT FROM WHERE (((", ALLOWLIST)
    assert not result.ok


def test_lint_warnings_are_non_blocking() -> None:
    # requête valide mais mal stylée (minuscules, pas d'espace) -> ne doit
    # jamais faire échouer la validation, seulement ajouter des avertissements
    result = validate_sql("select order_id from orders", ALLOWLIST)
    assert result.ok


def test_union_all_of_selects_is_accepted() -> None:
    sql = "SELECT order_id FROM orders UNION ALL SELECT customer_id FROM customers"
    result = validate_sql(sql, ALLOWLIST)
    assert result.ok, result.reason


def test_union_applies_limit_to_combined_result() -> None:
    sql = "SELECT order_id FROM orders UNION ALL SELECT customer_id FROM customers"
    result = validate_sql(sql, ALLOWLIST, max_limit=50)
    assert result.ok
    assert result.sql is not None
    assert "LIMIT 50" in result.sql


def test_union_still_rejects_ddl_in_a_branch() -> None:
    sql = "SELECT order_id FROM orders UNION ALL SELECT 1"
    # une branche légitime : ok. Vérifie qu'une injection DDL dans un union
    # multi-statements reste bloquée par le garde-fou "une seule instruction".
    result = validate_sql(sql + "; DROP TABLE orders;", ALLOWLIST)
    assert not result.ok


def test_union_rejects_unknown_table_in_either_branch() -> None:
    sql = "SELECT order_id FROM orders UNION ALL SELECT x FROM secret_table"
    result = validate_sql(sql, ALLOWLIST)
    assert not result.ok


def test_validate_sql_accepts_duckdb_dialect() -> None:
    result = validate_sql("SELECT order_id FROM orders", ALLOWLIST, dialect="duckdb")
    assert result.ok, result.reason
