"""Journal d'audit léger (Phase 1 : SQL, Phase 2 : code Python) : trace
question -> code généré -> statut (accepté / rejeté / erreur d'exécution).
Format JSONL append-only, un fichier par type. Sera étendu en journal
immuable avec identité utilisateur et coûts Bedrock en Phase 6 ; dès
maintenant, aucun rejet ni aucune erreur n'est silencieux."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_LOGS_DIR = Path(__file__).resolve().parents[3] / "data" / "logs"
AUDIT_LOG_PATH = _LOGS_DIR / "sql_audit.jsonl"
PYTHON_AUDIT_LOG_PATH = _LOGS_DIR / "python_audit.jsonl"


@dataclass(frozen=True)
class AuditEntry:
    question: str
    raw_sql: str | None
    validated_sql: str | None
    status: str  # "accepted" | "rejected" | "execution_error"
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    reason: str | None = None
    row_count: int | None = None
    attempt: int = 1


def log_audit_entry(entry: AuditEntry, path: Path = AUDIT_LOG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

    if entry.status == "rejected":
        logger.warning("SQL rejeté (tentative %d): %s", entry.attempt, entry.reason)
    elif entry.status == "execution_error":
        logger.error("Erreur d'exécution SQL (tentative %d): %s", entry.attempt, entry.reason)
    else:
        logger.info("SQL accepté et exécuté (%s lignes)", entry.row_count)


@dataclass(frozen=True)
class PythonAuditEntry:
    question: str
    code: str
    status: str  # "accepted" | "execution_error"
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    reason: str | None = None
    attempt: int = 1


def log_python_audit_entry(entry: PythonAuditEntry, path: Path = PYTHON_AUDIT_LOG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

    if entry.status == "execution_error":
        logger.error("Erreur d'exécution Python (tentative %d): %s", entry.attempt, entry.reason)
    else:
        logger.info("Code Python accepté et exécuté (tentative %d)", entry.attempt)
