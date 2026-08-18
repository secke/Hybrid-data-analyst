"""Script de santé : vérifie chaque service du socle (Phase 0), y compris un
appel Bedrock réel. Sortie claire par service, code de sortie non-zéro si un
service échoue - aucun échec silencieux.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass

import redis
import requests
from minio import Minio
from rich.console import Console
from rich.table import Table
from sqlalchemy import text

from agent.db.postgres import get_admin_engine
from agent.llm.bedrock_client import BedrockClient
from agent.llm.embeddings import TitanEmbeddingsClient
from agent.observability.langfuse_client import get_langfuse_client
from config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def check_postgres() -> CheckResult:
    try:
        engine = get_admin_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return CheckResult("Postgres", True, "SELECT 1 OK")
    except Exception as exc:  # noqa: BLE001
        return CheckResult("Postgres", False, str(exc))


def check_qdrant() -> CheckResult:
    settings = get_settings()
    try:
        response = requests.get(settings.qdrant_url, timeout=5)
        response.raise_for_status()
        version = response.json().get("version", "?")
        return CheckResult("Qdrant", True, f"version {version}")
    except Exception as exc:  # noqa: BLE001
        return CheckResult("Qdrant", False, str(exc))


def check_minio() -> CheckResult:
    settings = get_settings()
    try:
        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        missing = [
            b for b in (settings.minio_bucket_artifacts,) if not client.bucket_exists(b)
        ]
        if missing:
            return CheckResult("MinIO", False, f"buckets manquants: {missing}")
        return CheckResult("MinIO", True, f"bucket '{settings.minio_bucket_artifacts}' présent")
    except Exception as exc:  # noqa: BLE001
        return CheckResult("MinIO", False, str(exc))


def check_redis() -> CheckResult:
    settings = get_settings()
    try:
        client = redis.from_url(settings.redis_url)
        client.ping()
        return CheckResult("Redis", True, "PING OK")
    except Exception as exc:  # noqa: BLE001
        return CheckResult("Redis", False, str(exc))


def check_langfuse() -> CheckResult:
    try:
        client = get_langfuse_client()
        ok = client.auth_check()
        return CheckResult("Langfuse", bool(ok), "auth_check OK" if ok else "auth_check a échoué")
    except Exception as exc:  # noqa: BLE001
        return CheckResult("Langfuse", False, str(exc))


def check_bedrock_converse() -> CheckResult:
    try:
        client = BedrockClient()
        messages = [{"role": "user", "content": [{"text": "Reply with exactly: OK"}]}]
        result = client.converse(messages=messages)
        ok = "OK" in result.text
        detail = f"réponse='{result.text.strip()}' tokens_in={result.input_tokens}"
        return CheckResult("Bedrock (Claude)", ok, detail)
    except Exception as exc:  # noqa: BLE001
        return CheckResult("Bedrock (Claude)", False, str(exc))


def check_bedrock_embeddings() -> CheckResult:
    try:
        client = TitanEmbeddingsClient()
        result = client.embed("test de santé du système")
        ok = len(result.vector) > 0
        return CheckResult("Bedrock (Titan Embeddings)", ok, f"dimension={len(result.vector)}")
    except Exception as exc:  # noqa: BLE001
        return CheckResult("Bedrock (Titan Embeddings)", False, str(exc))


CHECKS: list[Callable[[], CheckResult]] = [
    check_postgres,
    check_qdrant,
    check_minio,
    check_redis,
    check_langfuse,
    check_bedrock_converse,
    check_bedrock_embeddings,
]


def run_all() -> list[CheckResult]:
    return [check() for check in CHECKS]


def print_report(results: list[CheckResult]) -> None:
    console = Console()
    table = Table(title="Santé du socle - Phase 0")
    table.add_column("Service")
    table.add_column("Statut")
    table.add_column("Détail")

    for result in results:
        status = "[green]OK[/green]" if result.ok else "[red]ÉCHEC[/red]"
        table.add_row(result.name, status, result.detail)

    console.print(table)


def main() -> int:
    logging.basicConfig(level=get_settings().log_level)
    results = run_all()
    print_report(results)
    failed = [r for r in results if not r.ok]
    if failed:
        logger.error("%d service(s) en échec: %s", len(failed), [r.name for r in failed])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
