#!/usr/bin/env python3
"""Lance les 6 questions de validation Phase 6
(evaluation/phase6_questions_report.md) contre le pipeline de rapport
traçable réel. Effectue de vrais appels Bedrock - à exécuter manuellement
par l'utilisateur, pas par l'agent de build.

Usage:
    export PYTHONPATH="src:."
    uv run python scripts/run_phase6_questions.py
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

from agent.audit.journal import verify_journal  # noqa: E402
from agent.report.cli import build_report  # noqa: E402
from config.settings import get_settings  # noqa: E402

QUESTIONS_FILE = Path(__file__).resolve().parents[1] / "evaluation" / "phase6_questions_report.md"
_QUESTION_LINE_RE = re.compile(r"^\d+\.\s+(.*)$")


def load_questions() -> list[str]:
    lines = QUESTIONS_FILE.read_text(encoding="utf-8").splitlines()
    return [m.group(1) for line in lines if (m := _QUESTION_LINE_RE.match(line))]


def main() -> int:
    logging.basicConfig(level=get_settings().log_level)
    console = Console()
    questions = load_questions()
    console.print(f"[bold]{len(questions)} questions chargées[/bold]\n")

    summary = Table(title="Résumé Phase 6 - rapports traçables")
    summary.add_column("#")
    summary.add_column("Question")
    summary.add_column("Statut")
    summary.add_column("PDF")

    failures = 0
    for i, question in enumerate(questions, start=1):
        console.rule(f"Question {i}/{len(questions)}")
        try:
            pdf_path, url = build_report(question, upload=False)
        except Exception as exc:  # noqa: BLE001 - une question ne doit jamais interrompre les autres
            console.print(f"[red]Erreur inattendue: {exc}[/red]")
            summary.add_row(str(i), question, "[red]ERREUR[/red]", "-")
            failures += 1
            continue

        console.print(f"[green]OK[/green] -> {pdf_path}")
        summary.add_row(str(i), question, "[green]OK[/green]", str(pdf_path))

    console.print()
    console.print(summary)

    verification = verify_journal()
    console.print(f"\n[bold]Vérification du journal d'audit immuable:[/bold] {verification}")
    if not verification.ok:
        console.print("[red]ALERTE: le journal d'audit a été altéré ![/red]")
        failures += 1

    if failures:
        console.print(f"\n[red]{failures} problème(s) détecté(s)[/red]")
    else:
        console.print(f"\n[green]Les {len(questions)} rapports ont été générés[/green]")
        console.print("[green]Journal d'audit intact[/green]")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
