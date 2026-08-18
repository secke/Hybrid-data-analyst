"""Orchestration Text-to-SQL complète : recherche du contexte de schéma
pertinent -> génération SQL -> validation -> exécution -> auto-correction sur
erreur (3 tentatives maximum), avec journalisation systématique."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from qdrant_client import QdrantClient

from agent.audit.log import AuditEntry, log_audit_entry
from agent.llm.protocols import BedrockConverser, Embedder
from agent.schema.introspect import TableSchema
from agent.schema.search import BM25SchemaIndex, hybrid_search
from agent.sql.executor import ExecutionResult, execute_readonly
from agent.sql.generator import generate_sql
from agent.sql.validator import ValidationResult, validate_sql

MAX_ATTEMPTS = 3
TOP_K_TABLES = 5


@dataclass(frozen=True)
class AttemptRecord:
    attempt: int
    raw_sql: str
    validation: ValidationResult
    execution: ExecutionResult | None


@dataclass(frozen=True)
class PipelineResult:
    question: str
    ok: bool
    sql: str | None
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    attempts: list[AttemptRecord] = field(default_factory=list)
    schema_context_tables: list[str] = field(default_factory=list)


def answer_question(
    question: str,
    *,
    bedrock_client: BedrockConverser,
    bm25_index: BM25SchemaIndex,
    embedder: Embedder,
    qdrant_client: QdrantClient,
    collection_name: str,
    allowlist: dict[str, set[str]],
    tables_by_name: dict[str, TableSchema],
    top_k: int = TOP_K_TABLES,
    max_attempts: int = MAX_ATTEMPTS,
) -> PipelineResult:
    relevant_names = hybrid_search(
        question, bm25_index, embedder, qdrant_client, collection_name, top_k=top_k
    )
    schema_context = "\n\n".join(
        tables_by_name[name].to_document() for name in relevant_names if name in tables_by_name
    )

    attempts: list[AttemptRecord] = []
    previous_sql: str | None = None
    previous_error: str | None = None

    for attempt_num in range(1, max_attempts + 1):
        raw_sql = generate_sql(
            question=question,
            schema_context=schema_context,
            client=bedrock_client,
            previous_sql=previous_sql,
            previous_error=previous_error,
        )

        validation = validate_sql(raw_sql, allowlist)
        if not validation.ok:
            log_audit_entry(
                AuditEntry(
                    question=question,
                    raw_sql=raw_sql,
                    validated_sql=None,
                    status="rejected",
                    reason=validation.reason,
                    attempt=attempt_num,
                )
            )
            attempts.append(AttemptRecord(attempt_num, raw_sql, validation, None))
            previous_sql, previous_error = raw_sql, validation.reason
            continue

        assert validation.sql is not None
        execution = execute_readonly(validation.sql)
        if not execution.ok:
            log_audit_entry(
                AuditEntry(
                    question=question,
                    raw_sql=raw_sql,
                    validated_sql=validation.sql,
                    status="execution_error",
                    reason=execution.error,
                    attempt=attempt_num,
                )
            )
            attempts.append(AttemptRecord(attempt_num, raw_sql, validation, execution))
            previous_sql, previous_error = validation.sql, execution.error
            continue

        log_audit_entry(
            AuditEntry(
                question=question,
                raw_sql=raw_sql,
                validated_sql=validation.sql,
                status="accepted",
                row_count=execution.row_count,
                attempt=attempt_num,
            )
        )
        attempts.append(AttemptRecord(attempt_num, raw_sql, validation, execution))
        return PipelineResult(
            question=question,
            ok=True,
            sql=validation.sql,
            columns=execution.columns,
            rows=execution.rows,
            row_count=execution.row_count,
            attempts=attempts,
            schema_context_tables=relevant_names,
        )

    return PipelineResult(
        question=question,
        ok=False,
        sql=None,
        attempts=attempts,
        schema_context_tables=relevant_names,
    )
