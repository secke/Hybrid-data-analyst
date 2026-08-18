"""Teste le journal d'audit immuable réellement (écriture sur disque,
chaînage de hash, détection de falsification). Aucun appel LLM."""

from __future__ import annotations

import json

from agent.audit.journal import JournalEntry, append_entry, current_identity, verify_journal


def _entry(question: str, **overrides: object) -> JournalEntry:
    defaults: dict[str, object] = {
        "question": question,
        "artifact_type": "sql",
        "artifact": "SELECT 1",
        "status": "accepted",
    }
    defaults.update(overrides)
    return JournalEntry(**defaults)  # type: ignore[arg-type]


def test_current_identity_returns_non_empty_string() -> None:
    assert current_identity()


def test_current_identity_respects_env_override(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("AGENT_USER_IDENTITY", "test-user")
    assert current_identity() == "test-user"


def test_verify_journal_ok_on_missing_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    result = verify_journal(path=tmp_path / "nonexistent.jsonl")
    assert result.ok
    assert result.entry_count == 0


def test_append_entry_writes_valid_chain(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "journal.jsonl"
    append_entry(_entry("Q1"), path=path)
    append_entry(_entry("Q2"), path=path)
    append_entry(_entry("Q3"), path=path)

    result = verify_journal(path=path)
    assert result.ok
    assert result.entry_count == 3


def test_append_entry_chains_prev_hash(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "journal.jsonl"
    hash1 = append_entry(_entry("Q1"), path=path)
    hash2 = append_entry(_entry("Q2"), path=path)
    assert hash1 != hash2

    lines = path.read_text(encoding="utf-8").splitlines()
    record2 = json.loads(lines[1])
    assert record2["prev_hash"] == hash1


def test_verify_journal_detects_tampered_content(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "journal.jsonl"
    append_entry(_entry("Q1", artifact="SELECT 1"), path=path)
    append_entry(_entry("Q2", artifact="SELECT 2"), path=path)

    lines = path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[1])
    record["artifact"] = "SELECT * FROM secret"  # falsification
    lines[1] = json.dumps(record)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = verify_journal(path=path)
    assert not result.ok
    assert result.broken_at_line == 2
    assert result.entry_count == 1


def test_verify_journal_detects_deleted_entry(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "journal.jsonl"
    append_entry(_entry("Q1"), path=path)
    append_entry(_entry("Q2"), path=path)
    append_entry(_entry("Q3"), path=path)

    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[1]  # supprime l'entrée du milieu
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = verify_journal(path=path)
    assert not result.ok


def test_journal_entry_carries_cost_and_tokens(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "journal.jsonl"
    append_entry(
        _entry(
            "Q1", model_id="claude-sonnet-4-5", input_tokens=100, output_tokens=20,
            estimated_cost_usd=0.0006,
        ),
        path=path,
    )
    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert record["input_tokens"] == 100
    assert record["output_tokens"] == 20
    assert record["estimated_cost_usd"] == 0.0006
