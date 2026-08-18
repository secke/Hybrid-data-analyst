#!/usr/bin/env python3
"""Lance les 10 questions de validation Phase 2
(evaluation/phase2_questions_northwind.md) contre le pipeline SQL + Python
réel. Effectue de vrais appels Bedrock - à exécuter manuellement par
l'utilisateur, pas par l'agent de build.

Usage:
    export PYTHONPATH="src:."
    uv run python scripts/run_phase2_questions.py
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from agent.python_exec.cli import ask_with_computation, print_python_result  # noqa: E402
from config.settings import get_settings  # noqa: E402

QUESTIONS_FILE = (
    Path(__file__).resolve().parents[1] / "evaluation" / "phase2_questions_northwind.md"
)
_SQL_LINE_RE = re.compile(r"^\d+\.\s+SQL:\s+(.*)$")
_CALCUL_LINE_RE = re.compile(r"^\s+Calcul:\s+(.*)$")


def load_question_pairs() -> list[tuple[str, str]]:
    lines = QUESTIONS_FILE.read_text(encoding="utf-8").splitlines()
    pairs: list[tuple[str, str]] = []
    pending_sql: str | None = None
    for line in lines:
        sql_match = _SQL_LINE_RE.match(line)
        if sql_match:
            pending_sql = sql_match.group(1)
            continue
        calcul_match = _CALCUL_LINE_RE.match(line)
        if calcul_match and pending_sql is not None:
            pairs.append((pending_sql, calcul_match.group(1)))
            pending_sql = None
    return pairs


def main() -> int:
    logging.basicConfig(level=get_settings().log_level)
    console = Console()
    pairs = load_question_pairs()
    console.print(f"[bold]{len(pairs)} paires de questions chargées[/bold]\n")

    summary = Table(title="Résumé Phase 2 - calcul au-delà du SQL")
    summary.add_column("#")
    summary.add_column("Calcul")
    summary.add_column("Statut")
    summary.add_column("Tentatives")

    failures = 0
    for i, (sql_question, computation_question) in enumerate(pairs, start=1):
        console.rule(f"Question {i}/{len(pairs)}")
        try:
            result = ask_with_computation(sql_question, computation_question)
        except Exception as exc:  # noqa: BLE001 - une question ne doit jamais interrompre les autres
            console.print(f"[red]Erreur inattendue: {exc}[/red]")
            summary.add_row(str(i), computation_question, "[red]ERREUR[/red]", "-")
            failures += 1
            continue

        print_python_result(console, computation_question, result)

        status = "[green]OK[/green]" if result.ok else "[red]ÉCHEC[/red]"
        if not result.ok:
            failures += 1
        summary.add_row(str(i), computation_question, status, str(len(result.attempts)))

    console.print()
    console.print(summary)
    if failures:
        console.print(f"\n[red]{failures}/{len(pairs)} question(s) en échec[/red]")
    else:
        console.print(f"\n[green]Les {len(pairs)} questions ont abouti[/green]")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
