"""Export PDF (WeasyPrint) : rapport avec tableau de données et, si fourni,
le graphique déjà généré en Phase 3 (image PNG existante, jamais régénérée
ici). Entièrement déterministe, aucune génération LLM."""

from __future__ import annotations

import base64
from pathlib import Path

import pandas as pd
from weasyprint import HTML

_TEMPLATE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: sans-serif; margin: 2cm; color: #1a1a1a; }}
  h1 {{ font-size: 20pt; border-bottom: 2px solid #2c5f8a; padding-bottom: 8px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 1em; font-size: 10pt; }}
  th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: left; }}
  th {{ background-color: #dce6f1; }}
  img {{ max-width: 100%; margin-top: 1em; }}
  .meta {{ color: #555; font-size: 9pt; margin-top: 0.5em; }}
</style>
</head>
<body>
  <h1>{title}</h1>
  <p class="meta">{subtitle}</p>
  {chart_html}
  {table_html}
</body>
</html>
"""


def write_pdf(
    path: Path,
    df: pd.DataFrame,
    *,
    title: str,
    subtitle: str = "",
    chart_png_bytes: bytes | None = None,
    max_rows: int = 200,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)

    chart_html = ""
    if chart_png_bytes:
        b64 = base64.b64encode(chart_png_bytes).decode("ascii")
        chart_html = f'<img src="data:image/png;base64,{b64}" alt="graphique">'

    table_html = df.head(max_rows).to_html(index=False, border=0)

    html_content = _TEMPLATE.format(
        title=title, subtitle=subtitle, chart_html=chart_html, table_html=table_html
    )
    HTML(string=html_content).write_pdf(str(path))
    return path
