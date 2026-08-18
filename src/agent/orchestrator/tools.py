"""Outils de l'agent (Phase 8) : chacun encapsule un pipeline déjà construit
et testé (Phases 1-6), sans dupliquer leur logique. Une fine couche de
routage/état est ajoutée ici pour l'orchestrateur LangGraph.

`TOOL_SPECS` fournit les schémas JSON attendus par `toolConfig` de l'API
Bedrock Converse (voir `agent.llm.bedrock_client.BedrockClient.converse_with_tools`).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

from agent.audit.journal import JournalEntry, append_entry, current_identity
from agent.export.csv_export import write_csv
from agent.export.excel import write_excel
from agent.export.pdf import write_pdf
from agent.export.storage import upload_artifact
from agent.federation.currency import fetch_rates
from agent.federation.pipeline import answer_federated_question
from agent.federation.reviews_synthesis import (
    reviews_available,
    sample_reviews,
    synthesize_reviews,
)
from agent.orchestrator.context import ToolContext
from agent.orchestrator.state import SessionState, ToolExecution
from agent.python_exec.cli import sql_rows_to_dataframe
from agent.python_exec.pipeline import answer_with_computation
from agent.report.generator import generate_narrative
from agent.report.pdf import write_traceable_report_pdf
from agent.sql.pipeline import answer_question
from agent.viz.pipeline import generate_chart
from agent.viz.storage import save_chart
from agent.viz.vision import comment_on_chart
from config.settings import get_settings

EXPORT_DIR = Path(__file__).resolve().parents[3] / "data" / "artifacts" / "exports"
REPORT_DIR = Path(__file__).resolve().parents[3] / "data" / "artifacts" / "reports"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "artifact"


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal | datetime | date):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(v) for v in value]
    return value


def _dataframe_preview(df: pd.DataFrame, max_rows: int = 20) -> list[dict[str, Any]]:
    return [_json_safe(row) for row in df.head(max_rows).to_dict(orient="records")]


def _track_cost(state: SessionState, category: str, question: str, artifact_type: str) -> None:
    """Journalise l'appel Bedrock qui vient d'avoir lieu sur `state.bedrock_client`
    dans le journal immuable (Phase 6), avec la catégorie d'outil pour le
    suivi de coût (Phase 7)."""
    usage = state.bedrock_client.last_result
    append_entry(
        JournalEntry(
            question=question,
            artifact_type=artifact_type,
            artifact=state.last_sql,
            status="accepted",
            model_id=state.bedrock_client.last_model_id,
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
            estimated_cost_usd=state.bedrock_client.last_cost_usd or 0.0,
            category=category,
        )
    )


# --------------------------------------------------------------------------
# 1. query_data (Phase 1)
# --------------------------------------------------------------------------


def tool_query_data(ctx: ToolContext, state: SessionState, question: str) -> ToolExecution:
    settings = get_settings()
    result = answer_question(
        question,
        bedrock_client=state.bedrock_client,
        bm25_index=ctx.bm25_index,
        embedder=ctx.embedder,
        qdrant_client=ctx.qdrant_client,
        collection_name=settings.qdrant_collection,
        allowlist=ctx.allowlist,
        tables_by_name=ctx.tables_by_name,
    )
    _track_cost(state, "query_data", question, "sql")

    if not result.ok:
        return ToolExecution(
            llm_summary={"ok": False, "error": "Échec de génération SQL après 3 tentatives."}
        )

    df = sql_rows_to_dataframe(result.columns, result.rows)
    state.last_dataframe = df
    state.last_sql = result.sql
    state.last_source = "northwind"

    return ToolExecution(
        llm_summary={
            "ok": True,
            "sql": result.sql,
            "row_count": result.row_count,
            "columns": result.columns,
            "preview_rows": _dataframe_preview(df),
        },
        display={"sql": result.sql, "dataframe": df},
    )


# --------------------------------------------------------------------------
# 2. query_federated_data (Phase 5)
# --------------------------------------------------------------------------


def tool_query_federated_data(
    ctx: ToolContext, state: SessionState, question: str
) -> ToolExecution:
    con, tables_by_name, allowlist = ctx.federated()

    extra_context = ""
    try:
        rates = fetch_rates("GBP")
        extra_context = (
            f"Taux de change actuels: 1 GBP = {rates.get('USD')} USD, {rates.get('EUR')} EUR."
        )
    except Exception:  # noqa: BLE001 - le contexte devise est un bonus, pas bloquant
        pass

    result = answer_federated_question(
        question,
        con=con,
        bedrock_client=state.bedrock_client,
        tables=list(tables_by_name.values()),
        allowlist=allowlist,
        extra_context=extra_context,
    )
    _track_cost(state, "query_federated_data", question, "sql")

    if not result.ok:
        return ToolExecution(
            llm_summary={
                "ok": False,
                "error": "Échec de génération SQL fédéré après 3 tentatives.",
            }
        )

    df = pd.DataFrame(result.rows, columns=result.columns)
    state.last_dataframe = df
    state.last_sql = result.sql
    state.last_source = "federated"

    return ToolExecution(
        llm_summary={
            "ok": True,
            "sql": result.sql,
            "row_count": result.row_count,
            "columns": result.columns,
            "preview_rows": _dataframe_preview(df),
        },
        display={"sql": result.sql, "dataframe": df},
    )


# --------------------------------------------------------------------------
# 3. compute (Phase 2)
# --------------------------------------------------------------------------


def tool_compute(ctx: ToolContext, state: SessionState, question: str) -> ToolExecution:
    if state.last_dataframe is None:
        return ToolExecution(
            llm_summary={
                "ok": False,
                "error": (
                    "Aucune donnée chargée : appelle query_data ou "
                    "query_federated_data d'abord."
                ),
            }
        )

    result = answer_with_computation(
        question, state.last_dataframe, bedrock_client=state.bedrock_client
    )
    _track_cost(state, "compute", question, "python")

    if not result.ok:
        return ToolExecution(
            llm_summary={"ok": False, "error": "Échec du calcul Python après 3 tentatives."}
        )

    if result.result_dataframe is not None:
        summary: dict[str, Any] = {
            "ok": True,
            "result_type": "dataframe",
            "preview_rows": _dataframe_preview(result.result_dataframe),
        }
    else:
        summary = {"ok": True, "result_type": "value", "result": _json_safe(result.result_value)}

    return ToolExecution(
        llm_summary=summary,
        display={
            "code": result.code,
            "result_dataframe": result.result_dataframe,
            "result_value": result.result_value,
        },
    )


# --------------------------------------------------------------------------
# 4. visualize (Phase 3)
# --------------------------------------------------------------------------


def tool_visualize(ctx: ToolContext, state: SessionState, question: str) -> ToolExecution:
    if state.last_dataframe is None:
        return ToolExecution(
            llm_summary={
                "ok": False,
                "error": (
                    "Aucune donnée chargée : appelle query_data ou "
                    "query_federated_data d'abord."
                ),
            }
        )

    chart_result = generate_chart(
        question, state.last_dataframe, bedrock_client=state.bedrock_client
    )
    _track_cost(state, "visualize", question, "chart")

    if not chart_result.ok or chart_result.chart_png_bytes is None:
        return ToolExecution(
            llm_summary={
                "ok": False,
                "error": "Échec de génération du graphique après 3 tentatives.",
            }
        )

    saved = save_chart(chart_result.chart_png_bytes, chart_result.chart_html or "")
    commentary = comment_on_chart(
        question, chart_result.chart_png_bytes, state.bedrock_client
    )
    _track_cost(state, "visualize", question, "vision")

    state.last_chart_png = chart_result.chart_png_bytes
    state.last_chart_question = question

    return ToolExecution(
        llm_summary={"ok": True, "commentary": commentary},
        display={
            "chart_png": chart_result.chart_png_bytes,
            "png_path": str(saved.png_path),
            "html_path": str(saved.html_path),
            "commentary": commentary,
        },
    )


# --------------------------------------------------------------------------
# 5. export_files (Phase 4)
# --------------------------------------------------------------------------


def tool_export_files(ctx: ToolContext, state: SessionState, formats: list[str]) -> ToolExecution:
    if state.last_dataframe is None:
        return ToolExecution(
            llm_summary={
                "ok": False,
                "error": (
                    "Aucune donnée chargée : appelle query_data ou "
                    "query_federated_data d'abord."
                ),
            }
        )

    df = state.last_dataframe
    slug = _slugify(state.last_sql or "export")
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    urls: dict[str, str] = {}

    if "xlsx" in formats:
        chart_sheet = "Donnees" if len(df.columns) >= 2 and len(df) > 0 else None
        path = write_excel(
            EXPORT_DIR / f"{slug}.xlsx", sheets={"Donnees": df}, chart_sheet=chart_sheet
        )
        urls["xlsx"] = upload_artifact(path).url
    if "csv" in formats:
        path = write_csv(EXPORT_DIR / f"{slug}.csv", df)
        urls["csv"] = upload_artifact(path).url
    if "pdf" in formats:
        path = write_pdf(EXPORT_DIR / f"{slug}.pdf", df, title=state.last_sql or "Export")
        urls["pdf"] = upload_artifact(path).url

    return ToolExecution(llm_summary={"ok": True, "files": urls}, display={"files": urls})


# --------------------------------------------------------------------------
# 6. generate_report (Phase 6)
# --------------------------------------------------------------------------


def tool_generate_report(ctx: ToolContext, state: SessionState, question: str) -> ToolExecution:
    if state.last_dataframe is None:
        return ToolExecution(
            llm_summary={
                "ok": False,
                "error": (
                    "Aucune donnée chargée : appelle query_data ou "
                    "query_federated_data d'abord."
                ),
            }
        )

    narrative = generate_narrative(
        question, state.last_dataframe, state.bedrock_client, sql=state.last_sql
    )
    _track_cost(state, "generate_report", question, "report")

    usage = state.bedrock_client.last_result
    cost = state.bedrock_client.last_cost_usd
    trace_metadata = {
        "identity": current_identity(),
        "model_id": state.bedrock_client.last_model_id or "",
        "input_tokens": str(usage.input_tokens if usage else 0),
        "output_tokens": str(usage.output_tokens if usage else 0),
        "estimated_cost_usd": f"{cost:.6f}" if cost is not None else "N/A",
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = write_traceable_report_pdf(
        REPORT_DIR / f"{_slugify(question)}.pdf",
        title=question,
        narrative=narrative,
        df=state.last_dataframe,
        sql=state.last_sql,
        chart_png_bytes=state.last_chart_png,
        trace_metadata=trace_metadata,
    )
    url = upload_artifact(pdf_path).url

    return ToolExecution(
        llm_summary={"ok": True, "narrative": narrative, "report_url": url},
        display={"narrative": narrative, "pdf_path": str(pdf_path), "url": url},
    )


# --------------------------------------------------------------------------
# 7. synthesize_reviews (Phase 5)
# --------------------------------------------------------------------------


def tool_synthesize_reviews(ctx: ToolContext, state: SessionState) -> ToolExecution:
    if not reviews_available():
        return ToolExecution(
            llm_summary={
                "ok": False,
                "error": "Aucun échantillon d'avis disponible (ingestion Kaggle non effectuée).",
            }
        )

    df = sample_reviews()
    synthesis = synthesize_reviews(df, state.bedrock_client)
    _track_cost(state, "synthesize_reviews", "synthèse des avis", "reviews")

    return ToolExecution(
        llm_summary={"ok": True, "synthesis": synthesis}, display={"synthesis": synthesis}
    )


# --------------------------------------------------------------------------
# Registre des outils + spécifications Bedrock
# --------------------------------------------------------------------------

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "toolSpec": {
            "name": "query_data",
            "description": (
                "Répond à une question métier en récupérant des données depuis Northwind "
                "(base ERP/CRM : clients, commandes, produits, employés, fournisseurs...) "
                "via une requête SQL générée et exécutée. Utilise cet outil pour toute "
                "question portant uniquement sur les données Northwind."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "La question en langage naturel",
                        }
                    },
                    "required": ["question"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "query_federated_data",
            "description": (
                "Répond à une question qui nécessite de combiner Northwind ET Online Retail II "
                "(export e-commerce réel, en GBP) - comparaisons cross-source, conversion de "
                "devise, résolution de noms de pays entre les deux sources."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {"question": {"type": "string"}},
                    "required": ["question"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "compute",
            "description": (
                "Effectue un calcul Python (statistiques, corrélation, régression, agrégation "
                "avancée...) sur les données récupérées par le dernier appel à query_data ou "
                "query_federated_data. Nécessite d'avoir déjà récupéré des données."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "Le calcul à effectuer",
                        }
                    },
                    "required": ["question"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "visualize",
            "description": (
                "Génère un graphique à partir des données récupérées par le dernier appel à "
                "query_data ou query_federated_data, et fournit un commentaire ancré sur "
                "l'image réelle produite. Nécessite d'avoir déjà récupéré des données."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "Le graphique à produire"}
                    },
                    "required": ["question"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "export_files",
            "description": (
                "Exporte les données récupérées par le dernier appel à query_data ou "
                "query_federated_data en fichiers téléchargeables (Excel, CSV, PDF). "
                "Nécessite d'avoir déjà récupéré des données."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "formats": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["xlsx", "csv", "pdf"]},
                            "description": "Formats désirés",
                        }
                    },
                    "required": ["formats"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "generate_report",
            "description": (
                "Génère un rapport narratif PDF traçable (chaque affirmation référence une "
                "ligne du tableau de données) à partir des données du dernier appel à "
                "query_data ou query_federated_data, avec le graphique le plus récent si "
                "disponible. Nécessite d'avoir déjà récupéré des données."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {"question": {"type": "string"}},
                    "required": ["question"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "synthesize_reviews",
            "description": (
                "Produit une synthèse qualitative d'un échantillon d'avis clients Amazon "
                "(sentiment général, points positifs/négatifs récurrents). Ne prend aucun "
                "paramètre."
            ),
            "inputSchema": {"json": {"type": "object", "properties": {}}},
        }
    },
]
