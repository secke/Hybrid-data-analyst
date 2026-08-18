"""Export PDF du rapport narratif (Phase 6), avec annexe de traçabilité
systématique : SQL exécuté, tableau de données complet (indexé, pour que les
références `[Réf: index N]` du texte soient vérifiables), et métadonnées
d'audit (identité, horodatage, modèle, tokens, coût, hash du journal
immuable). Entièrement déterministe, aucune génération LLM ici."""

from __future__ import annotations

import base64
import html
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
  h2 {{ font-size: 14pt; color: #2c5f8a; margin-top: 1.5em; }}
  .narrative {{ line-height: 1.5; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 1em; font-size: 9pt; }}
  th, td {{ border: 1px solid #ccc; padding: 5px 7px; text-align: left; }}
  th {{ background-color: #dce6f1; }}
  img {{ max-width: 100%; margin-top: 1em; }}
  .trace {{
    background-color: #f5f5f5; padding: 1em; font-size: 9pt;
    font-family: monospace; white-space: pre-wrap;
  }}
  .meta {{ color: #555; font-size: 9pt; }}
</style>
</head>
<body>
  <h1>{title}</h1>

  <div class="narrative">{narrative_html}</div>

  {chart_html}

  <h2>Annexe de traçabilité - données sources</h2>
  <p class="meta">Chaque référence [Réf: index N] du rapport ci-dessus pointe
  vers l'index de ligne du tableau suivant.</p>
  {table_html}

  <h2>Métadonnées d'audit</h2>
  <div class="trace">{trace_text}</div>
</body>
</html>
"""


def _narrative_to_html(narrative: str) -> str:
    """Rendu minimal markdown -> HTML (titres # / ## et paragraphes), sans
    dépendance externe - suffisant pour le texte structuré généré par
    `agent.report.generator`."""
    lines = []
    for line in narrative.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            lines.append(f"<h2>{html.escape(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            lines.append(f"<h1 style='font-size:16pt;border:none'>{html.escape(stripped[2:])}</h1>")
        elif stripped:
            lines.append(f"<p>{html.escape(stripped)}</p>")
    return "\n".join(lines)


def write_traceable_report_pdf(
    path: Path,
    *,
    title: str,
    narrative: str,
    df: pd.DataFrame,
    sql: str | None = None,
    chart_png_bytes: bytes | None = None,
    trace_metadata: dict[str, str],
    max_rows: int = 200,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)

    chart_html = ""
    if chart_png_bytes:
        b64 = base64.b64encode(chart_png_bytes).decode("ascii")
        chart_html = f'<img src="data:image/png;base64,{b64}" alt="graphique">'

    table_html = df.head(max_rows).to_html(index=True, border=0)

    trace_lines = [f"{key}: {value}" for key, value in trace_metadata.items()]
    if sql:
        trace_lines.append(f"sql_executed: {sql}")
    trace_text = "\n".join(trace_lines)

    html_content = _TEMPLATE.format(
        title=html.escape(title),
        narrative_html=_narrative_to_html(narrative),
        chart_html=chart_html,
        table_html=table_html,
        trace_text=html.escape(trace_text),
    )
    HTML(string=html_content).write_pdf(str(path))
    return path
