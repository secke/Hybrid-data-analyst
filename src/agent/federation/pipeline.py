"""Orchestration Text-to-SQL fédérée (Phase 5) : génération -> validation
(dialecte DuckDB) -> exécution -> auto-correction sur erreur (3 tentatives
maximum), avec journalisation systématique (même journal que la Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import duckdb

from agent.audit.log import AuditEntry, log_audit_entry
from agent.federation.executor import execute_federated
from agent.federation.generator import build_schema_context, generate_federated_sql
from agent.llm.protocols import BedrockConverser
from agent.schema.introspect import TableSchema
from agent.sql.executor import ExecutionResult
from agent.sql.validator import ValidationResult, validate_sql

MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class FederatedAttemptRecord:
    attempt: int
    raw_sql: str
    validation: ValidationResult
    execution: ExecutionResult | None


@dataclass(frozen=True)
class FederatedPipelineResult:
    question: str
    ok: bool
    sql: str | None
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    attempts: list[FederatedAttemptRecord] = field(default_factory=list)


def answer_federated_question(
    question: str,
    *,
    con: duckdb.DuckDBPyConnection,
    bedrock_client: BedrockConverser,
    tables: list[TableSchema],
    allowlist: dict[str, set[str]],
    max_attempts: int = MAX_ATTEMPTS,
    extra_context: str = "",
) -> FederatedPipelineResult:
    schema_context = build_schema_context(tables, extra_context)

    attempts: list[FederatedAttemptRecord] = []
    previous_sql: str | None = None
    previous_error: str | None = None

    for attempt_num in range(1, max_attempts + 1):
        raw_sql = generate_federated_sql(
            question=question,
            schema_context=schema_context,
            client=bedrock_client,
            previous_sql=previous_sql,
            previous_error=previous_error,
        )

        validation = validate_sql(raw_sql, allowlist, dialect="duckdb")
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
            attempts.append(FederatedAttemptRecord(attempt_num, raw_sql, validation, None))
            previous_sql, previous_error = raw_sql, validation.reason
            continue

        assert validation.sql is not None
        execution = execute_federated(con, validation.sql)
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
            attempts.append(FederatedAttemptRecord(attempt_num, raw_sql, validation, execution))
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
        attempts.append(FederatedAttemptRecord(attempt_num, raw_sql, validation, execution))
        return FederatedPipelineResult(
            question=question,
            ok=True,
            sql=validation.sql,
            columns=execution.columns,
            rows=execution.rows,
            row_count=execution.row_count,
            attempts=attempts,
        )

    return FederatedPipelineResult(question=question, ok=False, sql=None, attempts=attempts)
