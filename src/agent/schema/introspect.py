"""Introspection du schéma Postgres (colonnes + contraintes réelles).

Sert deux usages : produire les documents texte indexés pour la recherche
(Phase 1 - RAG schéma) et fournir l'allowlist tables/colonnes utilisée par le
validateur SQL pour rejeter toute référence à une table ou colonne
inexistante.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.engine import Engine

SCHEMA_NAME = "public"

_COLUMNS_QUERY = text(
    """
    SELECT table_name, column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_schema = :schema
    ORDER BY table_name, ordinal_position
    """
)

_CONSTRAINTS_QUERY = text(
    """
    SELECT
        conrelid::regclass::text AS table_name,
        conname,
        CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' END AS kind,
        pg_get_constraintdef(oid) AS definition
    FROM pg_constraint
    WHERE connamespace = (:schema)::regnamespace AND contype IN ('p', 'f')
    ORDER BY table_name
    """
)


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool


@dataclass(frozen=True)
class ConstraintInfo:
    name: str
    kind: str  # "PRIMARY KEY" | "FOREIGN KEY"
    definition: str


@dataclass(frozen=True)
class TableSchema:
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    constraints: list[ConstraintInfo] = field(default_factory=list)

    @property
    def column_names(self) -> set[str]:
        return {c.name for c in self.columns}

    def to_document(self) -> str:
        """Représentation texte utilisée pour l'indexation (BM25 + embeddings)."""
        lines = [f"Table: {self.name}", "Colonnes:"]
        for col in self.columns:
            nullability = "NULL" if col.nullable else "NOT NULL"
            lines.append(f"  - {col.name} ({col.data_type}, {nullability})")
        if self.constraints:
            lines.append("Contraintes:")
            for con in self.constraints:
                lines.append(f"  - {con.definition}")
        return "\n".join(lines)


def introspect_schema(engine: Engine, schema: str = SCHEMA_NAME) -> list[TableSchema]:
    """Lit le schéma réel depuis Postgres (colonnes + PK/FK). À exécuter avec
    le moteur en lecture seule (`get_readonly_engine`)."""
    tables: dict[str, TableSchema] = {}

    with engine.connect() as conn:
        for row in conn.execute(_COLUMNS_QUERY, {"schema": schema}):
            table = tables.setdefault(row.table_name, TableSchema(name=row.table_name))
            table.columns.append(
                ColumnInfo(
                    name=row.column_name,
                    data_type=row.data_type,
                    nullable=row.is_nullable == "YES",
                )
            )

        for row in conn.execute(_CONSTRAINTS_QUERY, {"schema": schema}):
            owning_table = tables.get(row.table_name)
            if owning_table is None:
                continue
            owning_table.constraints.append(
                ConstraintInfo(name=row.conname, kind=row.kind, definition=row.definition)
            )

    return sorted(tables.values(), key=lambda t: t.name)


def build_allowlist(tables: list[TableSchema]) -> dict[str, set[str]]:
    """table_name -> {colonnes} pour la validation SQL (garde-fous Phase 1)."""
    return {t.name: t.column_names for t in tables}
