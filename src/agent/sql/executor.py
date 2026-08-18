"""Exécution du SQL déjà validé (`validator.validate_sql`) sur le rôle
Postgres en lecture seule, avec statement_timeout (configuré sur le moteur,
voir `agent.db.postgres.get_readonly_engine`).

Utilise `text()` plutôt que `exec_driver_sql` : ce dernier envoie le SQL
brut au driver psycopg, qui applique son style de paramètres natif
("pyformat") même sans paramètre fourni - tout `%` littéral (très courant
dans un LIKE '%...%') fait alors planter l'exécution avec une erreur
"only '%s', '%b', '%t' are allowed as placeholders" (constaté en Phase 7).
`text()` gère correctement à la fois les `%` littéraux et les `:` à
l'intérieur de chaînes (les seuls `:` hors chaîne possibles, ex. `::cast`,
sont de toute façon réécrits en `CAST(... AS ...)` par le validateur - voir
tests `test_execute_readonly_handles_*`)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from agent.db.postgres import get_readonly_engine

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionResult:
    ok: bool
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    error: str | None = None


def execute_readonly(sql: str) -> ExecutionResult:
    """N'exécute jamais de SQL qui n'a pas d'abord été accepté par
    `validate_sql` - cette fonction ne refait aucune vérification de
    sécurité."""
    engine = get_readonly_engine()
    try:
        with engine.connect() as conn:
            cursor_result = conn.execute(text(sql))
            columns = list(cursor_result.keys())
            rows = [dict(zip(columns, row, strict=True)) for row in cursor_result.fetchall()]
        return ExecutionResult(ok=True, columns=columns, rows=rows, row_count=len(rows))
    except SQLAlchemyError as exc:
        logger.warning("Échec d'exécution SQL: %s", exc)
        return ExecutionResult(ok=False, error=str(exc))
