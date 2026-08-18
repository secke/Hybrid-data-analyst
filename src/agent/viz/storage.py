"""Sauvegarde locale des graphiques générés (PNG + HTML interactif). Le
stockage définitif via MinIO avec URLs pré-signées arrive en Phase 4 ; pour
l'instant, les artefacts sont écrits sur disque pour que l'utilisateur
puisse les ouvrir directement."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

CHARTS_DIR = Path(__file__).resolve().parents[3] / "data" / "artifacts" / "charts"


@dataclass(frozen=True)
class SavedChart:
    png_path: Path
    html_path: Path


def save_chart(
    png_bytes: bytes,
    html_content: str,
    name: str | None = None,
    directory: Path = CHARTS_DIR,
) -> SavedChart:
    directory.mkdir(parents=True, exist_ok=True)
    chart_id = name or uuid.uuid4().hex[:12]
    png_path = directory / f"{chart_id}.png"
    html_path = directory / f"{chart_id}.html"
    png_path.write_bytes(png_bytes)
    html_path.write_text(html_content, encoding="utf-8")
    return SavedChart(png_path=png_path, html_path=html_path)
