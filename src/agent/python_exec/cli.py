"""CLI combiné SQL + Python (Phase 2) : récupère des données via le
pipeline Text-to-SQL (Phase 1), puis exécute dessus une analyse Python dans
le sandbox isolé (Phase 2).

Effectue de vrais appels Bedrock (génération SQL + génération Python) - à
lancer manuellement par l'utilisateur, voir README section Phase 2.
"""

from __future__ import annotations

import argparse
import logging

import pandas as pd
from rich.console import Console

from agent.llm.bedrock_client import BedrockClient
from agent.python_exec.pipeline import PythonPipelineResult, answer_with_computation
from agent.sql.cli import ask as ask_sql
from config.settings import get_settings

logger = logging.getLogger(__name__)


def sql_rows_to_dataframe(columns: list[str], rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=columns)


def print_python_result(console: Console, question: str, result: PythonPipelineResult) -> None:
    console.print(f"\n[bold]Question (calcul):[/bold] {question}")

    for attempt in result.attempts:
        status = "[green]OK[/green]" if attempt.execution.ok else "[red]ÉCHEC[/red]"
        console.print(f"\nTentative {attempt.attempt}: {status}")
        console.print(attempt.code)
        if not attempt.execution.ok:
            console.print(f"  -> {attempt.execution.error}")

    if not result.ok:
        console.print("\n[red]Échec après 3 tentatives.[/red]")
        return

    console.print("\n[bold]Résultat:[/bold]")
    if result.result_dataframe is not None:
        console.print(result.result_dataframe.to_string())
    else:
        console.print(result.result_value)


def ask_with_computation(sql_question: str, computation_question: str) -> PythonPipelineResult:
    sql_result = ask_sql(sql_question)
    if not sql_result.ok:
        raise RuntimeError(f"Impossible de récupérer les données pour: {sql_question!r}")

    df = sql_rows_to_dataframe(sql_result.columns, sql_result.rows)
    bedrock_client = BedrockClient()
    return answer_with_computation(computation_question, df, bedrock_client=bedrock_client)


def main() -> None:
    logging.basicConfig(level=get_settings().log_level)
    parser = argparse.ArgumentParser(description="Question SQL suivie d'un calcul Python dessus")
    parser.add_argument("sql_question", help="Question pour récupérer les données (SQL, Phase 1)")
    parser.add_argument("computation_question", help="Question de calcul sur ces données (Python)")
    args = parser.parse_args()

    console = Console()
    result = ask_with_computation(args.sql_question, args.computation_question)
    print_python_result(console, args.computation_question, result)


if __name__ == "__main__":
    main()
