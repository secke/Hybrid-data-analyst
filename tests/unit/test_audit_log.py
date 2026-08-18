from __future__ import annotations

import json

from agent.audit.log import AuditEntry, PythonAuditEntry, log_audit_entry, log_python_audit_entry


def test_log_audit_entry_writes_valid_jsonl(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "audit.jsonl"
    entry = AuditEntry(
        question="Combien de clients ?",
        raw_sql="SELECT count(*) FROM customers",
        validated_sql="SELECT count(*) FROM customers LIMIT 1000",
        status="accepted",
        row_count=1,
    )

    log_audit_entry(entry, path=path)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["question"] == "Combien de clients ?"
    assert parsed["status"] == "accepted"


def test_log_audit_entry_appends(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "audit.jsonl"
    entry1 = AuditEntry(question="q1", raw_sql="s1", validated_sql="s1", status="accepted")
    entry2 = AuditEntry(question="q2", raw_sql="s2", validated_sql=None, status="rejected")
    log_audit_entry(entry1, path=path)
    log_audit_entry(entry2, path=path)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_log_audit_entry_creates_parent_directory(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "nested" / "audit.jsonl"
    entry = AuditEntry(question="q", raw_sql="s", validated_sql="s", status="accepted")
    log_audit_entry(entry, path=path)
    assert path.exists()


def test_rejected_entry_records_reason(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "audit.jsonl"
    log_audit_entry(
        AuditEntry(
            question="q", raw_sql="DROP TABLE orders", validated_sql=None,
            status="rejected", reason="Seules les requêtes SELECT sont autorisées",
        ),
        path=path,
    )
    parsed = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert parsed["reason"] == "Seules les requêtes SELECT sont autorisées"


def test_log_python_audit_entry_writes_valid_jsonl(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "python_audit.jsonl"
    entry = PythonAuditEntry(
        question="Somme des montants ?",
        code="result = df['amount'].sum()",
        status="accepted",
    )

    log_python_audit_entry(entry, path=path)

    parsed = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert parsed["question"] == "Somme des montants ?"
    assert parsed["status"] == "accepted"


def test_log_python_audit_entry_records_execution_error(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "python_audit.jsonl"
    log_python_audit_entry(
        PythonAuditEntry(
            question="q", code="result = df['amont'].sum()",
            status="execution_error", reason="KeyError: 'amont'", attempt=1,
        ),
        path=path,
    )
    parsed = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert parsed["status"] == "execution_error"
    assert "amont" in parsed["reason"]
