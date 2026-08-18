"""CLI de question cross-source (Phase 5) : fédère Northwind + Online Retail
II (+ avis Amazon si disponibles) via DuckDB, génère et exécute le SQL
fédéré, affiche le résultat, et ajoute une synthèse qualitative des avis si
l'échantillon est disponible.

Effectue de vrais appels Bedrock (génération SQL fédérée, et synthèse des
avis si demandée) - à lancer manuellement par l'utilisateur, voir README
section Phase 5.
"""

from __future__ import annotations

import argparse
import logging

from rich.console import Console
from rich.table import Table

from agent.federation.currency import fetch_rates
from agent.federation.duckdb_conn import get_federated_connection
from agent.federation.introspect import introspect_federated_schema
from agent.federation.pipeline import FederatedPipelineResult, answer_federated_question
from agent.federation.reviews_synthesis import (
    reviews_available,
    sample_reviews,
    synthesize_reviews,
)
from agent.llm.bedrock_client import BedrockClient
from agent.schema.introspect import build_allowlist
from config.settings import get_settings

logger = logging.getLogger(__name__)


def _build_currency_context() -> str:
    try:
        rates = fetch_rates("GBP")
        usd = rates.get("USD")
        eur = rates.get("EUR")
        return f"Taux de change actuels: 1 GBP = {usd} USD, 1 GBP = {eur} EUR."
    except Exception:  # noqa: BLE001 - le contexte devise est un bonus, pas bloquant
        logger.exception("Impossible de récupérer les taux de change (ignoré)")
        return ""


def print_result(console: Console, question: str, result: FederatedPipelineResult) -> None:
    console.print(f"[bold]Question:[/bold] {question}")

    for attempt in result.attempts:
        status = "[green]OK[/green]" if attempt.validation.ok else "[red]REJETÉ[/red]"
        console.print(f"\nTentative {attempt.attempt}: {status}")
        console.print(attempt.raw_sql)
        if not attempt.validation.ok:
            console.print(f"  -> {attempt.validation.reason}")
        elif attempt.execution is not None and not attempt.execution.ok:
            console.print(f"  -> erreur d'exécution: {attempt.execution.error}")

    if not result.ok:
        console.print("\n[red]Échec après 3 tentatives.[/red]")
        return

    console.print(f"\n[bold]SQL final:[/bold]\n{result.sql}\n")

    table = Table(title=f"{result.row_count} ligne(s)")
    for col in result.columns:
        table.add_column(col)
    for row in result.rows[:50]:
        table.add_row(*(str(row[c]) for c in result.columns))
    console.print(table)


def ask(question: str) -> FederatedPipelineResult:
    con = get_federated_connection()
    tables = introspect_federated_schema(con)
    allowlist = build_allowlist(tables)
    bedrock_client = BedrockClient()
    extra_context = _build_currency_context()

    return answer_federated_question(
        question,
        con=con,
        bedrock_client=bedrock_client,
        tables=tables,
        allowlist=allowlist,
        extra_context=extra_context,
    )


def ask_with_reviews_synthesis(question: str) -> tuple[FederatedPipelineResult, str | None]:
    result = ask(question)
    if not reviews_available():
        return result, None
    bedrock_client = BedrockClient()
    df = sample_reviews()
    synthesis = synthesize_reviews(df, bedrock_client)
    return result, synthesis


def main() -> None:
    logging.basicConfig(level=get_settings().log_level)
    parser = argparse.ArgumentParser(
        description="Question cross-source federee (Northwind + Online Retail II)"
    )
    parser.add_argument("question")
    parser.add_argument(
        "--with-reviews",
        action="store_true",
        help="Ajoute une synthese qualitative des avis clients si disponible",
    )
    args = parser.parse_args()

    console = Console()
    if args.with_reviews:
        result, synthesis = ask_with_reviews_synthesis(args.question)
    else:
        result, synthesis = ask(args.question), None

    print_result(console, args.question, result)
    if synthesis:
        console.print(f"\n[bold]Synthèse qualitative des avis:[/bold]\n{synthesis}")
    elif args.with_reviews:
        console.print(
            "\n[yellow]Aucun échantillon d'avis disponible "
            "(ingestion Kaggle non effectuée).[/yellow]"
        )


if __name__ == "__main__":
    main()
