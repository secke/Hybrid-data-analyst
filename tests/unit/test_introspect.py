"""Teste l'introspection contre le vrai Postgres local (docker-compose).
Aucun appel LLM. Nécessite `docker compose up -d postgres` et Northwind
chargé (`agent.ingestion.load_northwind`)."""

from __future__ import annotations

from agent.db.postgres import get_readonly_engine
from agent.schema.introspect import build_allowlist, introspect_schema


def test_introspect_schema_finds_northwind_tables() -> None:
    tables = introspect_schema(get_readonly_engine())
    table_names = {t.name for t in tables}
    assert {"orders", "customers", "order_details", "products"} <= table_names


def test_introspect_schema_captures_columns() -> None:
    tables = introspect_schema(get_readonly_engine())
    orders = next(t for t in tables if t.name == "orders")
    assert "order_id" in orders.column_names
    assert "customer_id" in orders.column_names


def test_introspect_schema_captures_foreign_keys() -> None:
    tables = introspect_schema(get_readonly_engine())
    orders = next(t for t in tables if t.name == "orders")
    fk_definitions = " ".join(c.definition for c in orders.constraints if c.kind == "FOREIGN KEY")
    assert "customers" in fk_definitions


def test_build_allowlist_maps_tables_to_columns() -> None:
    tables = introspect_schema(get_readonly_engine())
    allowlist = build_allowlist(tables)
    assert "orders" in allowlist
    assert "order_id" in allowlist["orders"]


def test_to_document_is_non_empty_text() -> None:
    tables = introspect_schema(get_readonly_engine())
    orders = next(t for t in tables if t.name == "orders")
    doc = orders.to_document()
    assert "Table: orders" in doc
    assert "order_id" in doc
