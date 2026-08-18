"""Teste l'exécution en lecture seule contre le vrai Postgres local. Aucun
appel LLM. Nécessite `docker compose up -d postgres` et Northwind chargé."""

from __future__ import annotations

from agent.sql.executor import execute_readonly


def test_execute_readonly_returns_rows() -> None:
    result = execute_readonly("SELECT order_id FROM orders ORDER BY order_id LIMIT 3")
    assert result.ok
    assert result.row_count == 3
    assert result.columns == ["order_id"]


def test_execute_readonly_handles_syntax_error_without_raising() -> None:
    result = execute_readonly("SELECT FROM WHERE (((")
    assert not result.ok
    assert result.error is not None


def test_execute_readonly_rejects_write_at_the_role_level() -> None:
    # Défense en profondeur : même si le validateur était contourné, le rôle
    # Postgres agent_readonly n'a de toute façon pas le droit d'écrire.
    result = execute_readonly("DELETE FROM orders WHERE order_id = 1")
    assert not result.ok


def test_execute_readonly_handles_colon_in_string_literal() -> None:
    # Vérifie qu'un littéral contenant ':' n'est pas interprété comme un
    # bind param (voir commentaire dans executor.py).
    result = execute_readonly("SELECT '14:30:00' AS t")
    assert result.ok
    assert result.rows == [{"t": "14:30:00"}]


def test_execute_readonly_handles_percent_in_like_pattern() -> None:
    # Régression Phase 7 : psycopg interprète '%' comme un placeholder de
    # style pyformat via exec_driver_sql - un LIKE '%...%' (très courant)
    # faisait planter l'exécution. Voir commentaire dans executor.py.
    sql = "SELECT company_name FROM customers WHERE company_name LIKE 'A%' LIMIT 1"
    result = execute_readonly(sql)
    assert result.ok
    assert len(result.rows) == 1


def test_execute_readonly_handles_double_colon_cast() -> None:
    result = execute_readonly("SELECT (1)::numeric AS x")
    assert result.ok
    assert result.rows[0]["x"] == 1
