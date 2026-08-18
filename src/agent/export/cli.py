"""CLI d'export (Phase 4) : récupère des données via le pipeline Text-to-SQL
(Phase 1), génère Excel/CSV/PDF, les téléverse sur MinIO et affiche les URLs
pré-signées.

Appelle réellement Bedrock (génération SQL) - à lancer manuellement par
l'utilisateur, voir README section Phase 4. La génération des fichiers et
l'upload MinIO eux-mêmes sont entièrement déterministes (aucun appel LLM).
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

from rich.console import Console

from agent.export.csv_export import write_csv
from agent.export.excel import write_excel
from agent.export.pdf import write_pdf
from agent.export.storage import upload_artifact
from agent.python_exec.cli import sql_rows_to_dataframe
from agent.sql.cli import ask as ask_sql
from config.settings import get_settings

logger = logging.getLogger(__name__)

EXPORT_DIR = Path(__file__).resolve().parents[3] / "data" / "artifacts" / "exports"
SUPPORTED_FORMATS = ("xlsx", "csv", "pdf")


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "export"


def _finalize(path: Path, upload: bool) -> str:
    if not upload:
        return str(path)
    uploaded = upload_artifact(path)
    return uploaded.url


def export_question(
    question: str, *, formats: tuple[str, ...] = SUPPORTED_FORMATS, upload: bool = True
) -> dict[str, str]:
    """Récupère les données via le pipeline SQL (Phase 1) puis génère les
    fichiers demandés. Retourne un dict format -> URL pré-signée (ou chemin
    local si `upload=False`)."""
    sql_result = ask_sql(question)
    if not sql_result.ok:
        raise RuntimeError(f"Impossible de récupérer les données pour: {question!r}")

    df = sql_rows_to_dataframe(sql_result.columns, sql_result.rows)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slugify(question)

    outputs: dict[str, str] = {}

    if "xlsx" in formats:
        chart_sheet = "Donnees" if len(df.columns) >= 2 and len(df) > 0 else None
        path = write_excel(
            EXPORT_DIR / f"{slug}.xlsx",
            sheets={"Donnees": df},
            chart_sheet=chart_sheet,
            chart_title=question,
            metadata={"question": question, "sql": sql_result.sql or ""},
        )
        outputs["xlsx"] = _finalize(path, upload)

    if "csv" in formats:
        path = write_csv(EXPORT_DIR / f"{slug}.csv", df)
        outputs["csv"] = _finalize(path, upload)

    if "pdf" in formats:
        path = write_pdf(EXPORT_DIR / f"{slug}.pdf", df, title=question)
        outputs["pdf"] = _finalize(path, upload)

    return outputs


def main() -> None:
    logging.basicConfig(level=get_settings().log_level)
    parser = argparse.ArgumentParser(
        description="Exporte le resultat d'une question en Excel/CSV/PDF"
    )
    parser.add_argument("question")
    parser.add_argument(
        "--formats", nargs="+", default=list(SUPPORTED_FORMATS), choices=list(SUPPORTED_FORMATS)
    )
    parser.add_argument(
        "--no-upload", action="store_true", help="Ne pas televerser sur MinIO, garder en local"
    )
    args = parser.parse_args()

    console = Console()
    outputs = export_question(
        args.question, formats=tuple(args.formats), upload=not args.no_upload
    )
    for fmt, location in outputs.items():
        console.print(f"[bold]{fmt}:[/bold] {location}")


if __name__ == "__main__":
    main()
