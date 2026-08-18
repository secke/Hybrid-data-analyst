"""Ressources partagées de l'orchestrateur (Phase 8), construites une fois
par session (schéma introspecté, index BM25, connexions) - coûteuses à
reconstruire à chaque appel d'outil. La fédération DuckDB (Phase 5) est
construite paresseusement (seulement si un outil cross-source est appelé)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from qdrant_client import QdrantClient

from agent.db.postgres import get_readonly_engine
from agent.federation.duckdb_conn import get_federated_connection
from agent.federation.introspect import introspect_federated_schema
from agent.llm.embeddings import TitanEmbeddingsClient
from agent.schema.indexer import get_qdrant_client
from agent.schema.introspect import TableSchema, build_allowlist, introspect_schema
from agent.schema.search import BM25SchemaIndex


@dataclass
class ToolContext:
    tables_by_name: dict[str, TableSchema]
    allowlist: dict[str, set[str]]
    bm25_index: BM25SchemaIndex
    embedder: TitanEmbeddingsClient
    qdrant_client: QdrantClient

    _federated_con: Any = field(default=None, repr=False)
    _federated_tables_by_name: dict[str, TableSchema] | None = field(default=None, repr=False)
    _federated_allowlist: dict[str, set[str]] | None = field(default=None, repr=False)

    @classmethod
    def build(cls) -> ToolContext:
        tables = introspect_schema(get_readonly_engine())
        return cls(
            tables_by_name={t.name: t for t in tables},
            allowlist=build_allowlist(tables),
            bm25_index=BM25SchemaIndex(tables),
            embedder=TitanEmbeddingsClient(),
            qdrant_client=get_qdrant_client(),
        )

    def federated(self) -> tuple[Any, dict[str, TableSchema], dict[str, set[str]]]:
        if self._federated_con is None:
            self._federated_con = get_federated_connection()
            federated_tables = introspect_federated_schema(self._federated_con)
            self._federated_tables_by_name = {t.name: t for t in federated_tables}
            self._federated_allowlist = build_allowlist(federated_tables)
        assert self._federated_tables_by_name is not None
        assert self._federated_allowlist is not None
        return self._federated_con, self._federated_tables_by_name, self._federated_allowlist
