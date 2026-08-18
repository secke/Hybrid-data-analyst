"""CLI de rapport traçable (Phase 6) : question -> SQL (Phase 1) -> rapport
narratif référençant systématiquement les données (Bedrock) -> PDF avec
annexe de traçabilité -> upload MinIO -> entrée dans le journal d'audit
immuable, tracée dans Langfuse (coût inclus).

Effectue de vrais appels Bedrock (génération SQL + génération narrative) -
à lancer manuellement par l'utilisateur, voir README section Phase 6.
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

from rich.console import Console

from agent.audit.journal import JournalEntry, append_entry, current_identity
from agent.export.storage import upload_artifact
from agent.observability.traced_bedrock import TracedBedrockClient
from agent.python_exec.cli import sql_rows_to_dataframe
from agent.report.generator import generate_narrative
from agent.report.pdf import write_traceable_report_pdf
from agent.sql.cli import ask as ask_sql
from config.settings import get_settings

logger = logging.getLogger(__name__)

REPORT_DIR = Path(__file__).resolve().parents[3] / "data" / "artifacts" / "reports"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "report"


def build_report(question: str, *, upload: bool = True) -> tuple[Path, str | None]:
    """Retourne (chemin_local_pdf, url_pré-signée_ou_None)."""
    sql_result = ask_sql(question)
    if not sql_result.ok:
        raise RuntimeError(f"Impossible de récupérer les données pour: {question!r}")

    df = sql_rows_to_dataframe(sql_result.columns, sql_result.rows)

    traced_client = TracedBedrockClient()
    narrative = generate_narrative(question, df, traced_client, sql=sql_result.sql)

    identity = current_identity()
    usage = traced_client.last_result
    cost = traced_client.last_cost_usd
    trace_metadata = {
        "identity": identity,
        "model_id": traced_client.last_model_id or "",
        "input_tokens": str(usage.input_tokens if usage else 0),
        "output_tokens": str(usage.output_tokens if usage else 0),
        "estimated_cost_usd": f"{cost:.6f}" if cost is not None else "N/A",
    }

    journal_hash = append_entry(
        JournalEntry(
            question=question,
            artifact_type="report",
            artifact=sql_result.sql,
            status="accepted",
            identity=identity,
            model_id=traced_client.last_model_id,
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
            estimated_cost_usd=traced_client.last_cost_usd or 0.0,
        )
    )
    trace_metadata["journal_hash"] = journal_hash

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = write_traceable_report_pdf(
        REPORT_DIR / f"{_slugify(question)}.pdf",
        title=question,
        narrative=narrative,
        df=df,
        sql=sql_result.sql,
        trace_metadata=trace_metadata,
    )

    if not upload:
        return pdf_path, None

    uploaded = upload_artifact(pdf_path)
    return pdf_path, uploaded.url


def main() -> None:
    logging.basicConfig(level=get_settings().log_level)
    parser = argparse.ArgumentParser(description="Genere un rapport narratif tracable en PDF")
    parser.add_argument("question")
    parser.add_argument(
        "--no-upload", action="store_true", help="Ne pas televerser sur MinIO, garder en local"
    )
    args = parser.parse_args()

    console = Console()
    pdf_path, url = build_report(args.question, upload=not args.no_upload)
    console.print(f"[bold]Rapport PDF:[/bold] {pdf_path}")
    if url:
        console.print(f"[bold]URL pré-signée:[/bold] {url}")


if __name__ == "__main__":
    main()
