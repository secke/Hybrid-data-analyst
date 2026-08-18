"""Journal d'audit immuable (Phase 6) : chaque entrée inclut le hash de
l'entrée précédente (chaîne de hachage), ce qui rend toute modification
rétroactive détectable via `verify_journal()`.

Contrairement aux journaux JSONL append-only des phases précédentes
(`agent.audit.log`), celui-ci trace explicitement l'identité de
l'utilisateur et le coût Bedrock estimé par requête - les deux exigences de
traçabilité propres à la Phase 6. Il ne remplace pas les journaux existants,
il les complète pour les artefacts où la traçabilité fine (identité, coût)
est requise (rapports, Phase 6).
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

JOURNAL_PATH = Path(__file__).resolve().parents[3] / "data" / "logs" / "immutable_journal.jsonl"
GENESIS_HASH = "0" * 64


def current_identity() -> str:
    """Identité de l'utilisateur courant. En l'absence d'un système d'auth
    complet (Keycloak n'est pas déployé dans ce projet - voir README), on
    utilise la variable d'environnement AGENT_USER_IDENTITY si définie,
    sinon l'utilisateur du système d'exploitation."""
    return os.environ.get("AGENT_USER_IDENTITY") or getpass.getuser()


@dataclass(frozen=True)
class JournalEntry:
    question: str
    artifact_type: str  # "sql" | "python" | "chart" | "report" | ...
    artifact: str | None  # le SQL exécuté, le code, etc. - None si rejeté avant validation
    status: str  # "accepted" | "rejected" | "execution_error"
    identity: str = field(default_factory=current_identity)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    model_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    reason: str | None = None
    category: str | None = None  # catégorie de question (Phase 7, suivi de coût par catégorie)


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False)


def _hash_entry(prev_hash: str, entry: JournalEntry) -> str:
    payload = _canonical_json(asdict(entry))
    return hashlib.sha256((prev_hash + payload).encode("utf-8")).hexdigest()


def _last_hash(path: Path) -> str:
    if not path.exists():
        return GENESIS_HASH
    last_line: str | None = None
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last_line = line
    if last_line is None:
        return GENESIS_HASH
    result: str = json.loads(last_line)["entry_hash"]
    return result


def append_entry(entry: JournalEntry, path: Path = JOURNAL_PATH) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    prev_hash = _last_hash(path)
    entry_hash = _hash_entry(prev_hash, entry)
    record = {"prev_hash": prev_hash, "entry_hash": entry_hash, **asdict(entry)}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return entry_hash


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    entry_count: int
    broken_at_line: int | None = None
    reason: str | None = None


def verify_journal(path: Path = JOURNAL_PATH) -> VerificationResult:
    """Rejoue toute la chaîne et recalcule chaque hash : détecte aussi bien
    une entrée modifiée qu'une entrée supprimée/réordonnée (le chaînage
    prev_hash -> entry_hash casse dans les deux cas)."""
    if not path.exists():
        return VerificationResult(ok=True, entry_count=0)

    expected_prev = GENESIS_HASH
    count = 0
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if record["prev_hash"] != expected_prev:
                return VerificationResult(
                    ok=False,
                    entry_count=count,
                    broken_at_line=line_no,
                    reason="Chaînage rompu: prev_hash ne correspond pas au hash précédent",
                )

            entry_fields = {
                k: v for k, v in record.items() if k not in ("prev_hash", "entry_hash")
            }
            entry = JournalEntry(**entry_fields)
            recomputed = _hash_entry(record["prev_hash"], entry)
            if recomputed != record["entry_hash"]:
                return VerificationResult(
                    ok=False,
                    entry_count=count,
                    broken_at_line=line_no,
                    reason="Hash invalide: le contenu de l'entrée a été modifié",
                )

            expected_prev = record["entry_hash"]
            count += 1

    return VerificationResult(ok=True, entry_count=count)
