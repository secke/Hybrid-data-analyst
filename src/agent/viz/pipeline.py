"""Orchestration de la génération de graphique (Phase 3) : génération de
code Plotly -> exécution dans le sandbox isolé -> auto-correction sur erreur
(3 tentatives maximum), avec journalisation systématique.

Une exécution sans erreur mais sans variable `fig` définie est traitée comme
un échec de tentative (le contrat de cette pipeline est de produire un
graphique, pas n'importe quel résultat)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from agent.audit.log import PythonAuditEntry, log_python_audit_entry
from agent.llm.protocols import BedrockConverser
from agent.sandbox.runner import SandboxResult, run_code
from agent.viz.generator import generate_chart_code
from config.settings import get_settings

MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class ChartAttemptRecord:
    attempt: int
    code: str
    execution: SandboxResult


@dataclass(frozen=True)
class ChartPipelineResult:
    question: str
    ok: bool
    code: str | None = None
    chart_png_bytes: bytes | None = None
    chart_html: str | None = None
    attempts: list[ChartAttemptRecord] = field(default_factory=list)


def _missing_chart_error(execution: SandboxResult) -> str | None:
    if execution.ok and execution.chart_png_bytes is None:
        return "Le code exécuté n'a pas défini de variable `fig` (graphique Plotly)"
    return None


def generate_chart(
    question: str,
    df: pd.DataFrame,
    *,
    bedrock_client: BedrockConverser,
    max_attempts: int = MAX_ATTEMPTS,
    sandbox_timeout_seconds: int | None = None,
) -> ChartPipelineResult:
    timeout = sandbox_timeout_seconds or get_settings().sandbox_chart_timeout_seconds
    attempts: list[ChartAttemptRecord] = []
    previous_code: str | None = None
    previous_error: str | None = None

    for attempt_num in range(1, max_attempts + 1):
        code = generate_chart_code(
            question=question,
            df=df,
            client=bedrock_client,
            previous_code=previous_code,
            previous_error=previous_error,
        )

        execution = run_code(code, input_df=df, timeout_seconds=timeout)
        missing_chart_error = _missing_chart_error(execution)
        effective_ok = execution.ok and missing_chart_error is None

        attempts.append(ChartAttemptRecord(attempt_num, code, execution))

        log_python_audit_entry(
            PythonAuditEntry(
                question=question,
                code=code,
                status="accepted" if effective_ok else "execution_error",
                reason=execution.error or missing_chart_error,
                attempt=attempt_num,
            )
        )

        if effective_ok:
            return ChartPipelineResult(
                question=question,
                ok=True,
                code=code,
                chart_png_bytes=execution.chart_png_bytes,
                chart_html=execution.chart_html,
                attempts=attempts,
            )

        previous_code = code
        previous_error = execution.error or missing_chart_error

    return ChartPipelineResult(question=question, ok=False, attempts=attempts)
