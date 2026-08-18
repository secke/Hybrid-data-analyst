"""Exécution isolée du code Python généré par le LLM (Phase 2).

Isolation : conteneur Docker `--rm`, sans réseau (`--network none`), FS
racine en lecture seule (seul `/workspace`, un tempdir hôte détruit après
chaque exécution, et `/tmp` en tmpfs restent inscriptibles), quotas
CPU/RAM/PID, utilisateur non-root, capacités Linux supprimées, timeout dur
avec `docker kill` en cas de dépassement.

Écart assumé par rapport au choix initial du projet ("réseau sortant limité
à l'endpoint Bedrock") : ce sandbox n'a AUCUN accès réseau, y compris vers
Bedrock. Le code d'analyse exécuté ici n'a jamais besoin d'appeler Bedrock
lui-même (seul l'orchestrateur, hors sandbox, le fait) ; zéro réseau est
strictement plus sûr et plus simple qu'un proxy avec allowlist. À revoir si
une phase future exige un appel Bedrock depuis l'intérieur du sandbox.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from config.settings import get_settings

logger = logging.getLogger(__name__)

WRAPPER_PATH = Path(__file__).resolve().parent.parent.parent.parent / "sandbox" / "exec_wrapper.py"


@dataclass(frozen=True)
class SandboxResult:
    ok: bool
    result_dataframe: pd.DataFrame | None = None
    result_value: Any = None
    chart_png_bytes: bytes | None = None
    chart_html: str | None = None
    error: str | None = None
    timed_out: bool = False


def _build_docker_command(container_name: str, tempdir: Path) -> list[str]:
    settings = get_settings()
    return [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "--network",
        "none",
        "--memory",
        settings.sandbox_memory_limit,
        "--cpus",
        settings.sandbox_cpu_limit,
        "--pids-limit",
        str(settings.sandbox_pids_limit),
        "--read-only",
        "--tmpfs",
        "/tmp:rw,size=64m",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        "1000:1000",
        # $HOME (image en lecture seule) n'est pas inscriptible : Chrome
        # headless (kaleido, export PNG des graphiques) y écrit son cache
        # crashpad et plante sinon. /tmp est le tmpfs inscriptible ci-dessus.
        # BROWSER_PATH pointe explicitement vers le Chrome installé au build
        # (voir sandbox/Dockerfile) car la détection automatique de kaleido
        # se base sur $HOME, qu'on vient de rediriger vers /tmp.
        "-e",
        "HOME=/tmp",
        "-e",
        "BROWSER_PATH=/home/sandboxuser/.local/share/choreographer/deps/chrome-linux64/chrome",
        "-v",
        f"{tempdir}:/workspace:rw",
        "-v",
        f"{WRAPPER_PATH}:/workspace/_wrapper.py:ro",
        "-w",
        "/workspace",
        settings.sandbox_image,
        "python",
        "/workspace/_wrapper.py",
    ]


def run_code(
    code: str,
    input_df: pd.DataFrame | None = None,
    timeout_seconds: int | None = None,
) -> SandboxResult:
    """Exécute `code` dans le sandbox isolé. `code` doit affecter son
    résultat à une variable `result` (DataFrame ou valeur JSON-sérialisable)
    et/ou une variable `fig` (plotly.graph_objects.Figure, Phase 3) - au
    moins l'une des deux doit être définie. `df` (issu de `input_df`) est
    disponible dans l'espace de noms du code.
    """
    settings = get_settings()
    timeout = timeout_seconds or settings.sandbox_timeout_seconds
    container_name = f"sandbox-{uuid.uuid4().hex[:12]}"

    with tempfile.TemporaryDirectory(prefix="sandbox-run-") as tmp:
        tempdir = Path(tmp)
        (tempdir / "code.py").write_text(code, encoding="utf-8")
        if input_df is not None:
            input_df.to_parquet(tempdir / "input.parquet")

        cmd = _build_docker_command(container_name, tempdir)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)  # noqa: S603
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "kill", container_name], capture_output=True)  # noqa: S603, S607
            logger.warning("Sandbox: timeout dépassé (%ss)", timeout)
            return SandboxResult(ok=False, error=f"Timeout dépassé ({timeout}s)", timed_out=True)

        return _collect_result(tempdir, proc)


OOM_KILLED_EXIT_CODE = 137  # 128 + SIGKILL, déclenché par le cgroup mémoire du conteneur


def _collect_result(tempdir: Path, proc: subprocess.CompletedProcess[str]) -> SandboxResult:
    error_path = tempdir / "error.txt"
    if proc.returncode != 0:
        if proc.returncode == OOM_KILLED_EXIT_CODE and not error_path.exists():
            settings = get_settings()
            error = (
                f"Le code a dépassé la limite mémoire du sandbox "
                f"({settings.sandbox_memory_limit}) et a été arrêté."
            )
        else:
            error = error_path.read_text(encoding="utf-8") if error_path.exists() else proc.stderr
        logger.warning("Sandbox: exécution en échec (code %s): %s", proc.returncode, error)
        return SandboxResult(ok=False, error=error or "Échec inconnu du conteneur sandbox")

    manifest_path = tempdir / "output_manifest.json"
    if not manifest_path.exists():
        return SandboxResult(
            ok=False, error="Le code exécuté n'a défini ni `result` ni `fig`"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    result_dataframe = None
    result_value = None
    if manifest.get("has_result"):
        if manifest.get("result_type") == "dataframe":
            result_dataframe = pd.read_parquet(tempdir / "output.parquet")
        else:
            result_value = json.loads((tempdir / "output.json").read_text(encoding="utf-8"))

    chart_png_bytes = None
    chart_html = None
    if manifest.get("has_chart"):
        chart_png_bytes = (tempdir / "chart.png").read_bytes()
        chart_html = (tempdir / "chart.html").read_text(encoding="utf-8")

    return SandboxResult(
        ok=True,
        result_dataframe=result_dataframe,
        result_value=result_value,
        chart_png_bytes=chart_png_bytes,
        chart_html=chart_html,
    )


def ensure_sandbox_image_exists() -> bool:
    settings = get_settings()
    result = subprocess.run(  # noqa: S603, S607
        ["docker", "image", "inspect", settings.sandbox_image],
        capture_output=True,
    )
    return result.returncode == 0


def check_docker_available() -> bool:
    return shutil.which("docker") is not None
