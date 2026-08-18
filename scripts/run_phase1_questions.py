#!/usr/bin/env python3
"""Lance les 20 questions de validation Phase 1 (evaluation/phase1_questions_northwind.md)
contre le pipeline Text-to-SQL réel. Effectue de vrais appels Bedrock - à
exécuter manuellement par l'utilisateur, pas par l'agent de build.

Usage:
    export PYTHONPATH="src:."
    uv run python scripts/run_phase1_questions.py
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

from agent.sql.cli import ask  # noqa: E402
from config.settings import get_settings  # noqa: E402

QUESTIONS_FILE = (
    Path(__file__).resolve().parents[1] / "evaluation" / "phase1_questions_northwind.md"
)
_QUESTION_LINE_RE = re.compile(r"^\d+\.\s+(.*)$")


def load_questions() -> list[str]:
    lines = QUESTIONS_FILE.read_text(encoding="utf-8").splitlines()
    return [m.group(1) for line in lines if (m := _QUESTION_LINE_RE.match(line))]


def main() -> int:
    logging.basicConfig(level=get_settings().log_level)
    console = Console()
    questions = load_questions()
    console.print(f"[bold]{len(questions)} questions chargées[/bold]\n")

    summary = Table(title="Résumé Phase 1 - 20 questions Northwind")
    summary.add_column("#")
    summary.add_column("Question")
    summary.add_column("Statut")
    summary.add_column("Tentatives")
    summary.add_column("Lignes")

    failures = 0
    for i, question in enumerate(questions, start=1):
        console.rule(f"Question {i}/{len(questions)}")
        try:
            result = ask(question)
        except Exception as exc:  # noqa: BLE001 - une question ne doit jamais interrompre les autres
            console.print(f"[red]Erreur inattendue: {exc}[/red]")
            summary.add_row(str(i), question, "[red]ERREUR[/red]", "-", "-")
            failures += 1
            continue

        console.print(f"[bold]{question}[/bold]")
        console.print(f"SQL: {result.sql}")
        console.print(f"Lignes: {result.row_count}")

        status = "[green]OK[/green]" if result.ok else "[red]ÉCHEC[/red]"
        if not result.ok:
            failures += 1
        summary.add_row(str(i), question, status, str(len(result.attempts)), str(result.row_count))

    console.print()
    console.print(summary)
    if failures:
        console.print(f"\n[red]{failures}/{len(questions)} question(s) en échec[/red]")
    else:
        console.print(f"\n[green]Les {len(questions)} questions ont abouti[/green]")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
