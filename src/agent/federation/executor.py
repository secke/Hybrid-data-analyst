"""Exécution du SQL fédéré déjà validé (`agent.sql.validator.validate_sql`
avec `dialect="duckdb"`) sur la connexion DuckDB fédérée. Même contrat que
`agent.sql.executor.execute_readonly` (réutilise `ExecutionResult`)."""

from __future__ import annotations

import logging

import duckdb

from agent.sql.executor import ExecutionResult

logger = logging.getLogger(__name__)


def execute_federated(con: duckdb.DuckDBPyConnection, sql: str) -> ExecutionResult:
    try:
        cursor = con.execute(sql)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        return ExecutionResult(ok=True, columns=columns, rows=rows, row_count=len(rows))
    except duckdb.Error as exc:
        logger.warning("Échec d'exécution SQL fédéré: %s", exc)
        return ExecutionResult(ok=False, error=str(exc))
