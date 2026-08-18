"""Export Excel multi-onglets avec mise en forme et graphique natif
(XlsxWriter). Entièrement déterministe : construit un classeur à partir de
DataFrames déjà calculés (résultats SQL/Python des phases précédentes),
aucune génération LLM ici."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import pandas as pd
import xlsxwriter

ChartType = Literal["column", "bar", "line", "pie"]

_INVALID_SHEET_CHARS = set("[]:*?/\\")


def _safe_sheet_name(name: str) -> str:
    cleaned = "".join(c for c in name if c not in _INVALID_SHEET_CHARS)
    return cleaned[:31] or "Feuille"


def _write_dataframe(worksheet: Any, df: pd.DataFrame, header_format: Any) -> None:
    for col_idx, col_name in enumerate(df.columns):
        worksheet.write(0, col_idx, str(col_name), header_format)
        col_lengths = df[col_name].astype(str).map(len).tolist()
        max_len = max([len(str(col_name)), *col_lengths], default=len(str(col_name)))
        worksheet.set_column(col_idx, col_idx, min(max_len + 2, 50))

    for row_idx, row in enumerate(df.itertuples(index=False), start=1):
        for col_idx, value in enumerate(row):
            worksheet.write(row_idx, col_idx, value)


def write_excel(
    path: Path,
    sheets: dict[str, pd.DataFrame],
    *,
    chart_sheet: str | None = None,
    chart_type: ChartType = "column",
    chart_title: str | None = None,
    metadata: dict[str, str] | None = None,
) -> Path:
    """Écrit un classeur XLSX avec un onglet par DataFrame de `sheets`, plus
    un onglet "Métadonnées" si `metadata` est fourni. Si `chart_sheet` est
    donné, ajoute un graphique natif Excel (lié aux 2 premières colonnes de
    ce DataFrame : catégories + valeurs), pas une image statique."""
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(str(path))
    header_format = workbook.add_format({"bold": True, "bg_color": "#DCE6F1", "border": 1})

    for sheet_name, df in sheets.items():
        worksheet = workbook.add_worksheet(_safe_sheet_name(sheet_name))
        _write_dataframe(worksheet, df, header_format)

        if sheet_name == chart_sheet and len(df.columns) >= 2 and len(df) > 0:
            chart = workbook.add_chart({"type": chart_type})
            n_rows = len(df)
            chart.add_series(
                {
                    "name": str(df.columns[1]),
                    "categories": [worksheet.get_name(), 1, 0, n_rows, 0],
                    "values": [worksheet.get_name(), 1, 1, n_rows, 1],
                }
            )
            if chart_title:
                chart.set_title({"name": chart_title})
            worksheet.insert_chart(1, len(df.columns) + 2, chart)

    if metadata:
        meta_sheet = workbook.add_worksheet("Metadonnees")
        meta_sheet.write_row(0, 0, ["Cle", "Valeur"], header_format)
        for i, (key, value) in enumerate(metadata.items(), start=1):
            meta_sheet.write_row(i, 0, [key, value])

    workbook.close()
    return path
