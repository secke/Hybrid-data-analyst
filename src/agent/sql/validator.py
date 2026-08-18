"""Garde-fous SQL obligatoires avant toute exécution (Phase 1).

Rejette : plusieurs instructions, tout ce qui n'est pas un SELECT, toute
référence à une table/colonne inexistante dans le schéma introspecté. Force
un LIMIT (injecté si absent, plafonné si trop élevé). Un lint SQLFluff est
appliqué en plus, à titre indicatif seulement (style, non bloquant).

`allowlist` doit provenir de `agent.schema.introspect.build_allowlist` sur le
schéma réellement introspecté - jamais d'une liste écrite à la main, pour
rester fidèle à l'état réel de la base.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import sqlfluff
import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError, SqlglotError
from sqlglot.optimizer.qualify import qualify

logger = logging.getLogger(__name__)

DIALECT = "postgres"
DEFAULT_MAX_LIMIT = 1000

_FORBIDDEN_NODE_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Grant,
)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    sql: str | None = None  # SQL final (LIMIT appliqué), None si rejeté
    reason: str | None = None  # raison du rejet, None si accepté
    lint_warnings: list[str] = field(default_factory=list)


def _lint_warnings(raw_sql: str, dialect: str) -> list[str]:
    try:
        violations = sqlfluff.lint(raw_sql, dialect=dialect)
    except Exception:  # noqa: BLE001 - un lint qui échoue ne doit jamais bloquer la validation
        logger.exception("Lint SQLFluff en échec (ignoré, non bloquant)")
        return []
    return [f"{v['code']}: {v['description']}" for v in violations]


def _apply_limit(statement: exp.Query, max_limit: int) -> exp.Query:
    existing = statement.args.get("limit")
    if existing is None:
        return statement.limit(max_limit)

    try:
        requested = int(existing.expression.this)
    except (AttributeError, ValueError, TypeError):
        requested = max_limit + 1  # valeur non lisible -> on replafonne par prudence

    if requested > max_limit:
        statement.set("limit", None)
        return statement.limit(max_limit)
    return statement


def validate_sql(
    raw_sql: str,
    allowlist: dict[str, set[str]],
    max_limit: int = DEFAULT_MAX_LIMIT,
    dialect: str = DIALECT,
) -> ValidationResult:
    """`dialect` : "postgres" (défaut, Phase 1) ou "duckdb" (Phase 5, requêtes
    fédérées). Les garde-fous (SELECT seul, une instruction, tables/colonnes
    réelles, LIMIT forcé) sont identiques quel que soit le dialecte."""
    cleaned = raw_sql.strip().rstrip(";").strip()
    if not cleaned:
        return ValidationResult(ok=False, reason="SQL vide")

    lint_warnings = _lint_warnings(cleaned, dialect)

    try:
        statements = [s for s in sqlglot.parse(cleaned, read=dialect) if s is not None]
    except SqlglotError as exc:
        # SqlglotError couvre ParseError (SQL syntaxiquement invalide) et
        # TokenError (ex: guillemet non fermé - payload d'injection type
        # "'; DROP TABLE ...; --") : les deux doivent être rejetés
        # proprement, jamais planter le validateur.
        return ValidationResult(ok=False, reason=f"Erreur de parsing SQL: {exc}")

    if len(statements) != 1:
        return ValidationResult(
            ok=False, reason=f"Une seule instruction SQL est autorisée (reçu: {len(statements)})"
        )

    statement = statements[0]

    if not isinstance(statement, exp.Select | exp.SetOperation):
        return ValidationResult(
            ok=False,
            reason=(
                "Seules les requêtes SELECT (ou UNION/INTERSECT/EXCEPT de SELECT) "
                f"sont autorisées (reçu: {type(statement).__name__})"
            ),
        )

    for node in statement.walk():
        node_expr = node[0] if isinstance(node, tuple) else node
        if isinstance(node_expr, _FORBIDDEN_NODE_TYPES):
            return ValidationResult(
                ok=False, reason=f"Instruction interdite détectée: {type(node_expr).__name__}"
            )

    referenced_tables = {t.name for t in statement.find_all(exp.Table)}
    unknown_tables = referenced_tables - allowlist.keys()
    if unknown_tables:
        return ValidationResult(ok=False, reason=f"Table(s) inconnue(s): {sorted(unknown_tables)}")

    schema: dict[str, object] = {
        table: dict.fromkeys(cols, "TEXT") for table, cols in allowlist.items()
    }
    try:
        qualified = qualify(statement, schema=schema, dialect=dialect)
    except OptimizeError as exc:
        return ValidationResult(ok=False, reason=f"Colonne ou référence invalide: {exc}")

    final_statement = _apply_limit(qualified, max_limit)
    final_sql = final_statement.sql(dialect=dialect)

    return ValidationResult(ok=True, sql=final_sql, lint_warnings=lint_warnings)
