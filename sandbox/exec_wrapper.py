"""Exécuté À L'INTÉRIEUR du conteneur sandbox (jamais importé côté hôte).

Charge `/workspace/input.parquet` (s'il existe) comme DataFrame `df`,
exécute `/workspace/code.py` dans un espace de noms contenant `df`, `pd` et
`np`, puis sérialise ce que le code a produit :
- variable `result` (Phase 2) : DataFrame -> output.parquet, sinon JSON-sérialisable -> output.json
- variable `fig` (Phase 3, plotly.graph_objects.Figure) : chart.png (export
  statique via kaleido) + chart.html (version interactive autonome)
- /workspace/output_manifest.json résume ce qui a été produit
- toute exception -> traceback complet dans /workspace/error.txt, code de sortie 1
- ni `result` ni `fig` définis -> considéré comme une erreur (code de sortie 1)
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any

WORKSPACE = Path("/workspace")


def _write_error(exc_info_text: str) -> None:
    (WORKSPACE / "error.txt").write_text(exc_info_text, encoding="utf-8")


def _serialize_result(namespace: dict[str, Any], manifest: dict[str, Any], pd: Any) -> None:
    if "result" not in namespace:
        return
    result = namespace["result"]
    if isinstance(result, pd.DataFrame):
        result.to_parquet(WORKSPACE / "output.parquet")
        manifest["result_type"] = "dataframe"
    else:
        try:
            payload = json.dumps(result, ensure_ascii=False, default=str)
        except TypeError:
            payload = json.dumps(str(result), ensure_ascii=False)
        (WORKSPACE / "output.json").write_text(payload, encoding="utf-8")
        manifest["result_type"] = "json"
    manifest["has_result"] = True


def _serialize_chart(namespace: dict[str, Any], manifest: dict[str, Any]) -> None:
    fig = namespace.get("fig")
    if fig is None:
        return
    fig.write_image(str(WORKSPACE / "chart.png"))
    fig.write_html(str(WORKSPACE / "chart.html"), include_plotlyjs="cdn")
    manifest["has_chart"] = True


def main() -> int:
    import pandas as pd

    df = None
    input_path = WORKSPACE / "input.parquet"
    if input_path.exists():
        df = pd.read_parquet(input_path)

    code = (WORKSPACE / "code.py").read_text(encoding="utf-8")

    namespace: dict[str, Any] = {"df": df, "pd": pd}
    try:
        import numpy as np

        namespace["np"] = np
    except ImportError:
        pass

    try:
        exec(compile(code, "<analysis_code>", "exec"), namespace)  # noqa: S102
    except Exception:
        _write_error(traceback.format_exc())
        return 1

    manifest: dict[str, Any] = {"has_result": False, "result_type": None, "has_chart": False}

    try:
        _serialize_result(namespace, manifest, pd)
        _serialize_chart(namespace, manifest)
    except Exception:
        _write_error(traceback.format_exc())
        return 1

    if not manifest["has_result"] and not manifest["has_chart"]:
        _write_error("Le code exécuté n'a défini ni `result` ni `fig`.")
        return 1

    (WORKSPACE / "output_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
