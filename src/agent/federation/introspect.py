"""Introspection du schéma fédéré (vues DuckDB : Northwind + sources
Parquet, voir `duckdb_conn.get_federated_connection`). Réutilise
`TableSchema`/`ColumnInfo`/`build_allowlist` de la Phase 1 pour rester
compatible avec le validateur SQL existant - seul le dialecte change."""

from __future__ import annotations

import duckdb

from agent.schema.introspect import ColumnInfo, TableSchema

_COLUMNS_QUERY = """
    SELECT table_name, column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_catalog = 'memory'
    ORDER BY table_name, ordinal_position
"""


def introspect_federated_schema(con: duckdb.DuckDBPyConnection) -> list[TableSchema]:
    tables: dict[str, TableSchema] = {}
    for table_name, column_name, data_type, is_nullable in con.execute(_COLUMNS_QUERY).fetchall():
        table = tables.setdefault(table_name, TableSchema(name=table_name))
        table.columns.append(
            ColumnInfo(name=column_name, data_type=data_type, nullable=is_nullable == "YES")
        )
    return sorted(tables.values(), key=lambda t: t.name)
