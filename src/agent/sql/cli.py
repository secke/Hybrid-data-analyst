"""CLI Text-to-SQL (Phase 1). Pose une question en langage naturel, affiche
chaque tentative (SQL + statut) et le résultat final.

Effectue de vrais appels Bedrock (Claude + Titan Embeddings) - à lancer
manuellement par l'utilisateur, voir README section Phase 1.
"""

from __future__ import annotations

import argparse
import logging

from qdrant_client.http.exceptions import UnexpectedResponse
from rich.console import Console
from rich.table import Table

from agent.db.postgres import get_readonly_engine
from agent.llm.bedrock_client import BedrockClient
from agent.llm.embeddings import TitanEmbeddingsClient
from agent.schema.indexer import get_qdrant_client
from agent.schema.introspect import TableSchema, build_allowlist, introspect_schema
from agent.schema.search import BM25SchemaIndex
from agent.sql.pipeline import PipelineResult, answer_question
from config.settings import get_settings

logger = logging.getLogger(__name__)


def build_schema_context() -> tuple[dict[str, TableSchema], dict[str, set[str]], BM25SchemaIndex]:
    tables = introspect_schema(get_readonly_engine())
    tables_by_name = {t.name: t for t in tables}
    allowlist = build_allowlist(tables)
    bm25 = BM25SchemaIndex(tables)
    return tables_by_name, allowlist, bm25


def print_result(console: Console, question: str, result: PipelineResult) -> None:
    console.print(f"[bold]Question:[/bold] {question}")
    tables_str = result.schema_context_tables
    console.print(f"[dim]Tables retenues par la recherche hybride: {tables_str}[/dim]")

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


def ask(question: str) -> PipelineResult:
    settings = get_settings()
    tables_by_name, allowlist, bm25 = build_schema_context()
    bedrock_client = BedrockClient()
    embedder = TitanEmbeddingsClient()
    qdrant_client = get_qdrant_client()

    if not qdrant_client.collection_exists(settings.qdrant_collection):
        raise RuntimeError(
            f"Collection Qdrant '{settings.qdrant_collection}' introuvable. "
            "Lancez d'abord: uv run python -m agent.schema.indexer"
        )

    return answer_question(
        question,
        bedrock_client=bedrock_client,
        bm25_index=bm25,
        embedder=embedder,
        qdrant_client=qdrant_client,
        collection_name=settings.qdrant_collection,
        allowlist=allowlist,
        tables_by_name=tables_by_name,
    )


def main() -> None:
    logging.basicConfig(level=get_settings().log_level)
    parser = argparse.ArgumentParser(description="Pose une question en langage naturel")
    parser.add_argument("question")
    args = parser.parse_args()

    console = Console()
    try:
        result = ask(args.question)
    except UnexpectedResponse as exc:
        console.print(f"[red]Erreur Qdrant: {exc}[/red]")
        raise SystemExit(1) from exc

    print_result(console, args.question, result)


if __name__ == "__main__":
    main()
