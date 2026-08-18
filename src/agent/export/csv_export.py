"""Export CSV (pandas). Déterministe, aucune génération LLM."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_csv(path: Path, df: pd.DataFrame) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path
