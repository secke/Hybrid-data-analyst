#!/usr/bin/env python3
"""Lance les 8 questions de validation Phase 3
(evaluation/phase3_questions_northwind.md) contre le pipeline SQL + graphique
+ vision réel. Effectue de vrais appels Bedrock - à exécuter manuellement
par l'utilisateur, pas par l'agent de build.

Usage:
    export PYTHONPATH="src:."
    uv run python scripts/run_phase3_questions.py
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

from agent.viz.cli import ask_with_chart, print_chart_result  # noqa: E402
from config.settings import get_settings  # noqa: E402

QUESTIONS_FILE = (
    Path(__file__).resolve().parents[1] / "evaluation" / "phase3_questions_northwind.md"
)
_SQL_LINE_RE = re.compile(r"^\d+\.\s+SQL:\s+(.*)$")
_CHART_LINE_RE = re.compile(r"^\s+Graphique:\s+(.*)$")


def load_question_pairs() -> list[tuple[str, str]]:
    lines = QUESTIONS_FILE.read_text(encoding="utf-8").splitlines()
    pairs: list[tuple[str, str]] = []
    pending_sql: str | None = None
    for line in lines:
        sql_match = _SQL_LINE_RE.match(line)
        if sql_match:
            pending_sql = sql_match.group(1)
            continue
        chart_match = _CHART_LINE_RE.match(line)
        if chart_match and pending_sql is not None:
            pairs.append((pending_sql, chart_match.group(1)))
            pending_sql = None
    return pairs


def main() -> int:
    logging.basicConfig(level=get_settings().log_level)
    console = Console()
    pairs = load_question_pairs()
    console.print(f"[bold]{len(pairs)} paires de questions chargées[/bold]\n")

    summary = Table(title="Résumé Phase 3 - graphique + relecture vision")
    summary.add_column("#")
    summary.add_column("Graphique")
    summary.add_column("Statut")
    summary.add_column("Tentatives")

    failures = 0
    for i, (sql_question, chart_question) in enumerate(pairs, start=1):
        console.rule(f"Question {i}/{len(pairs)}")
        try:
            output = ask_with_chart(sql_question, chart_question)
        except Exception as exc:  # noqa: BLE001 - une question ne doit jamais interrompre les autres
            console.print(f"[red]Erreur inattendue: {exc}[/red]")
            summary.add_row(str(i), chart_question, "[red]ERREUR[/red]", "-")
            failures += 1
            continue

        print_chart_result(console, chart_question, output.chart_result)
        if output.saved is not None:
            console.print(f"\n[bold]Graphique:[/bold] {output.saved.png_path}")
            console.print(f"[bold]Commentaire:[/bold] {output.commentary}")

        status = "[green]OK[/green]" if output.chart_result.ok else "[red]ÉCHEC[/red]"
        if not output.chart_result.ok:
            failures += 1
        summary.add_row(
            str(i), chart_question, status, str(len(output.chart_result.attempts))
        )

    console.print()
    console.print(summary)
    if failures:
        console.print(f"\n[red]{failures}/{len(pairs)} question(s) en échec[/red]")
    else:
        console.print(f"\n[green]Les {len(pairs)} questions ont abouti[/green]")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
