#!/usr/bin/env python3
"""Évaluation Phase 7 : exécute les 50 questions de référence (exactitude
d'exécution) + tests de robustesse contre le pipeline Text-to-SQL réel
(Phase 1), avec suivi de coût Bedrock par catégorie (Phase 6). Commande
unique et reproductible.

Effectue de vrais appels Bedrock (50 générations SQL) - à exécuter
manuellement par l'utilisateur, pas par l'agent de build.

Usage:
    export PYTHONPATH="src:."
    uv run python scripts/run_phase7_evaluation.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from agent.audit.journal import JournalEntry, append_entry  # noqa: E402
from agent.db.postgres import get_readonly_engine  # noqa: E402
from agent.evaluation.cost_report import (  # noqa: E402
    aggregate_cost_by_category,
    load_journal_entries,
)
from agent.evaluation.robustness import (  # noqa: E402
    all_injections_blocked,
    run_injection_resistance_check,
)
from agent.evaluation.scoring import compare_results  # noqa: E402
from agent.llm.embeddings import TitanEmbeddingsClient  # noqa: E402
from agent.observability.traced_bedrock import TracedBedrockClient  # noqa: E402
from agent.schema.indexer import get_qdrant_client  # noqa: E402
from agent.schema.introspect import build_allowlist, introspect_schema  # noqa: E402
from agent.schema.search import BM25SchemaIndex  # noqa: E402
from agent.sql.executor import execute_readonly  # noqa: E402
from agent.sql.pipeline import answer_question  # noqa: E402
from config.settings import get_settings  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parents[1] / "evaluation"
EVAL_DATASET_PATH = EVAL_DIR / "eval_dataset.json"
ROBUSTNESS_DATASET_PATH = EVAL_DIR / "robustness_dataset.json"
REPORT_OUTPUT_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "artifacts" / "eval_report.json"
)


def load_eval_dataset() -> list[dict]:  # type: ignore[type-arg]
    result: list[dict] = json.loads(EVAL_DATASET_PATH.read_text(encoding="utf-8"))  # type: ignore[type-arg]
    return result


def load_robustness_dataset() -> list[dict]:  # type: ignore[type-arg]
    result: list[dict] = json.loads(ROBUSTNESS_DATASET_PATH.read_text(encoding="utf-8"))  # type: ignore[type-arg]
    return result


def run_accuracy_evaluation(console: Console) -> list[dict]:  # type: ignore[type-arg]
    settings = get_settings()
    tables = introspect_schema(get_readonly_engine())
    allowlist = build_allowlist(tables)
    tables_by_name = {t.name: t for t in tables}
    bm25 = BM25SchemaIndex(tables)
    embedder = TitanEmbeddingsClient()
    qdrant_client = get_qdrant_client()

    if not qdrant_client.collection_exists(settings.qdrant_collection):
        raise RuntimeError(
            f"Collection Qdrant '{settings.qdrant_collection}' introuvable. "
            "Lancez d'abord: uv run python -m agent.schema.indexer"
        )

    dataset = load_eval_dataset()
    results = []

    for item in dataset:
        header = f"[{item['id']:2}/{len(dataset)}] {item['category']:16} {item['question'][:60]}"
        console.print(header)

        reference_execution = execute_readonly(item["sql"])
        if not reference_execution.ok:
            console.print(f"  [red]ERREUR SQL DE RÉFÉRENCE: {reference_execution.error}[/red]")
            results.append({**item, "correct": False, "error": "reference_sql_failed"})
            continue

        traced_client = TracedBedrockClient()
        start = time.time()
        try:
            pipeline_result = answer_question(
                item["question"],
                bedrock_client=traced_client,
                bm25_index=bm25,
                embedder=embedder,
                qdrant_client=qdrant_client,
                collection_name=settings.qdrant_collection,
                allowlist=allowlist,
                tables_by_name=tables_by_name,
            )
        except Exception as exc:  # noqa: BLE001 - une question ne doit jamais interrompre l'évaluation
            console.print(f"  [red]ERREUR INATTENDUE: {exc}[/red]")
            results.append({**item, "correct": False, "error": str(exc)})
            continue
        elapsed = time.time() - start

        correct = pipeline_result.ok and compare_results(
            reference_execution.rows, pipeline_result.rows
        )

        usage = traced_client.last_result
        append_entry(
            JournalEntry(
                question=item["question"],
                artifact_type="sql",
                artifact=pipeline_result.sql,
                status="accepted" if pipeline_result.ok else "rejected",
                model_id=traced_client.last_model_id,
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                estimated_cost_usd=traced_client.last_cost_usd or 0.0,
                category=item["category"],
            )
        )

        status = "[green]CORRECT[/green]" if correct else "[red]INCORRECT[/red]"
        console.print(f"  {status} ({elapsed:.1f}s, {len(pipeline_result.attempts)} tentative(s))")

        results.append(
            {
                "id": item["id"],
                "category": item["category"],
                "question": item["question"],
                "correct": correct,
                "generated_sql": pipeline_result.sql,
                "attempts": len(pipeline_result.attempts),
            }
        )

    return results


def run_robustness_evaluation(console: Console) -> dict:  # type: ignore[type-arg]
    console.rule("Résistance à l'injection SQL (déterministe, sans appel LLM)")
    injection_results = run_injection_resistance_check()
    for r in injection_results:
        status = "[green]BLOQUÉ[/green]" if r.blocked else "[red]NON BLOQUÉ - DANGER[/red]"
        console.print(f"  {status} | {r.payload[:60]}")
    injections_ok = all_injections_blocked(injection_results)

    console.rule("Colonnes inexistantes / hors périmètre / ambiguïté (jugement manuel requis)")
    from agent.sql.cli import ask

    qualitative_results = []
    for item in load_robustness_dataset():
        console.print(f"[{item['id']}] ({item['category']}) {item['question']}")
        console.print(f"  Note: {item['note']}")
        try:
            result = ask(item["question"])
            console.print(f"  ok={result.ok}, SQL={result.sql}")
            qualitative_results.append({"id": item["id"], "ok": result.ok, "sql": result.sql})
        except Exception as exc:  # noqa: BLE001 - comportement à examiner manuellement, pas un échec du runner
            console.print(f"  [yellow]Exception (comportement à examiner): {exc}[/yellow]")
            qualitative_results.append({"id": item["id"], "ok": False, "error": str(exc)})

    return {
        "injection_blocked_count": sum(1 for r in injection_results if r.blocked),
        "injection_total": len(injection_results),
        "injections_all_blocked": injections_ok,
        "qualitative_results": qualitative_results,
    }


def main() -> int:
    logging.basicConfig(level=get_settings().log_level)
    console = Console()

    console.rule("Phase 7 - Évaluation : exactitude d'exécution (50 questions)")
    accuracy_results = run_accuracy_evaluation(console)

    console.rule("Phase 7 - Évaluation : robustesse")
    robustness_results = run_robustness_evaluation(console)

    n_correct = sum(1 for r in accuracy_results if r.get("correct"))
    n_total = len(accuracy_results)
    overall_accuracy = n_correct / n_total if n_total else 0.0

    by_category: dict[str, list[dict]] = {}  # type: ignore[type-arg]
    for r in accuracy_results:
        by_category.setdefault(r["category"], []).append(r)

    summary = Table(title="Exactitude d'exécution par catégorie")
    summary.add_column("Catégorie")
    summary.add_column("Correct / Total")
    summary.add_column("Taux")
    for category, items in sorted(by_category.items()):
        correct = sum(1 for i in items if i.get("correct"))
        summary.add_row(category, f"{correct}/{len(items)}", f"{100 * correct / len(items):.0f}%")
    console.print()
    console.print(summary)
    pct = 100 * overall_accuracy
    console.print(f"\n[bold]Exactitude globale: {n_correct}/{n_total} ({pct:.1f}%)[/bold]")

    cost_entries = load_journal_entries()
    cost_report = aggregate_cost_by_category(cost_entries)
    cost_table = Table(title="Coût Bedrock par catégorie")
    cost_table.add_column("Catégorie")
    cost_table.add_column("Questions")
    cost_table.add_column("Tokens (in/out)")
    cost_table.add_column("Coût total")
    cost_table.add_column("Coût moyen")
    total_cost = 0.0
    for c in cost_report:
        cost_table.add_row(
            c.category,
            str(c.question_count),
            f"{c.total_input_tokens}/{c.total_output_tokens}",
            f"${c.total_cost_usd:.4f}",
            f"${c.avg_cost_usd:.4f}",
        )
        total_cost += c.total_cost_usd
    console.print()
    console.print(cost_table)
    console.print(f"\n[bold]Coût total estimé (cette évaluation): ${total_cost:.4f}[/bold]")

    injections = robustness_results["injection_blocked_count"]
    injections_total = robustness_results["injection_total"]
    console.print(f"\n[bold]Robustesse - injection SQL:[/bold] {injections}/{injections_total}")

    report = {
        "overall_accuracy": overall_accuracy,
        "n_correct": n_correct,
        "n_total": n_total,
        "accuracy_by_category": {
            category: sum(1 for i in items if i.get("correct")) / len(items)
            for category, items in by_category.items()
        },
        "cost_by_category": {
            c.category: {
                "question_count": c.question_count,
                "total_cost_usd": c.total_cost_usd,
                "avg_cost_usd": c.avg_cost_usd,
            }
            for c in cost_report
        },
        "total_cost_usd": total_cost,
        "robustness": robustness_results,
        "detailed_results": accuracy_results,
    }
    REPORT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report_json = json.dumps(report, ensure_ascii=False, indent=2)
    REPORT_OUTPUT_PATH.write_text(report_json, encoding="utf-8")
    console.print(f"\n[bold]Rapport complet:[/bold] {REPORT_OUTPUT_PATH}")

    return 0 if robustness_results["injections_all_blocked"] else 1


if __name__ == "__main__":
    sys.exit(main())
