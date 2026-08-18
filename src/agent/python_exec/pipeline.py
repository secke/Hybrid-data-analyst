"""Orchestration de l'analyse Python (Phase 2) : génération de code ->
exécution dans le sandbox isolé -> auto-correction sur erreur (3 tentatives
maximum), avec journalisation systématique de tout code exécuté."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from agent.audit.log import PythonAuditEntry, log_python_audit_entry
from agent.llm.protocols import BedrockConverser
from agent.python_exec.generator import generate_code
from agent.sandbox.runner import SandboxResult, run_code

MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class PythonAttemptRecord:
    attempt: int
    code: str
    execution: SandboxResult


@dataclass(frozen=True)
class PythonPipelineResult:
    question: str
    ok: bool
    code: str | None = None
    result_dataframe: pd.DataFrame | None = None
    result_value: Any = None
    attempts: list[PythonAttemptRecord] = field(default_factory=list)


def answer_with_computation(
    question: str,
    df: pd.DataFrame,
    *,
    bedrock_client: BedrockConverser,
    max_attempts: int = MAX_ATTEMPTS,
    sandbox_timeout_seconds: int | None = None,
) -> PythonPipelineResult:
    attempts: list[PythonAttemptRecord] = []
    previous_code: str | None = None
    previous_error: str | None = None

    for attempt_num in range(1, max_attempts + 1):
        code = generate_code(
            question=question,
            df=df,
            client=bedrock_client,
            previous_code=previous_code,
            previous_error=previous_error,
        )

        execution = run_code(code, input_df=df, timeout_seconds=sandbox_timeout_seconds)
        attempts.append(PythonAttemptRecord(attempt_num, code, execution))

        log_python_audit_entry(
            PythonAuditEntry(
                question=question,
                code=code,
                status="accepted" if execution.ok else "execution_error",
                reason=execution.error,
                attempt=attempt_num,
            )
        )

        if execution.ok:
            return PythonPipelineResult(
                question=question,
                ok=True,
                code=code,
                result_dataframe=execution.result_dataframe,
                result_value=execution.result_value,
                attempts=attempts,
            )

        previous_code, previous_error = code, execution.error

    return PythonPipelineResult(question=question, ok=False, attempts=attempts)
