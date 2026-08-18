"""CLI combiné SQL + graphique + commentaire vision (Phase 3) : récupère des
données via le pipeline Text-to-SQL (Phase 1), génère un graphique dessus
dans le sandbox isolé (Phase 3), puis demande à Claude (vision, Bedrock) un
commentaire ancré sur l'image PNG réellement produite.

Effectue de vrais appels Bedrock (génération SQL + génération de graphique +
vision) - à lancer manuellement par l'utilisateur, voir README section
Phase 3.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass

from rich.console import Console

from agent.llm.bedrock_client import BedrockClient
from agent.python_exec.cli import sql_rows_to_dataframe
from agent.sql.cli import ask as ask_sql
from agent.viz.pipeline import ChartPipelineResult, generate_chart
from agent.viz.storage import SavedChart, save_chart
from agent.viz.vision import comment_on_chart
from config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChartWithCommentary:
    chart_result: ChartPipelineResult
    commentary: str | None
    saved: SavedChart | None


def print_chart_result(console: Console, question: str, result: ChartPipelineResult) -> None:
    console.print(f"\n[bold]Question (graphique):[/bold] {question}")

    for attempt in result.attempts:
        success = attempt.execution.ok and attempt.execution.chart_png_bytes is not None
        status = "[green]OK[/green]" if success else "[red]ÉCHEC[/red]"
        console.print(f"\nTentative {attempt.attempt}: {status}")
        console.print(attempt.code)
        if not success:
            console.print(f"  -> {attempt.execution.error}")

    if not result.ok:
        console.print("\n[red]Échec après 3 tentatives.[/red]")


def ask_with_chart(sql_question: str, chart_question: str) -> ChartWithCommentary:
    sql_result = ask_sql(sql_question)
    if not sql_result.ok:
        raise RuntimeError(f"Impossible de récupérer les données pour: {sql_question!r}")

    df = sql_rows_to_dataframe(sql_result.columns, sql_result.rows)
    bedrock_client = BedrockClient()
    chart_result = generate_chart(chart_question, df, bedrock_client=bedrock_client)

    if not chart_result.ok or chart_result.chart_png_bytes is None:
        return ChartWithCommentary(chart_result=chart_result, commentary=None, saved=None)

    saved = save_chart(chart_result.chart_png_bytes, chart_result.chart_html or "")
    commentary = comment_on_chart(chart_question, chart_result.chart_png_bytes, bedrock_client)
    return ChartWithCommentary(chart_result=chart_result, commentary=commentary, saved=saved)


def main() -> None:
    logging.basicConfig(level=get_settings().log_level)
    parser = argparse.ArgumentParser(description="Question SQL suivie d'un graphique commenté")
    parser.add_argument("sql_question", help="Question pour récupérer les données (SQL, Phase 1)")
    parser.add_argument("chart_question", help="Question du graphique à produire (Phase 3)")
    args = parser.parse_args()

    console = Console()
    output = ask_with_chart(args.sql_question, args.chart_question)
    print_chart_result(console, args.chart_question, output.chart_result)

    if output.saved is not None:
        console.print(f"\n[bold]Graphique enregistré:[/bold] {output.saved.png_path}")
        console.print(f"[bold]Version interactive:[/bold] {output.saved.html_path}")
        console.print("\n[bold]Commentaire (vision, ancré sur l'image):[/bold]")
        console.print(output.commentary)


if __name__ == "__main__":
    main()
