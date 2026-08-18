from __future__ import annotations

from agent.audit.journal import JournalEntry, append_entry
from agent.evaluation.cost_report import aggregate_cost_by_category, load_journal_entries


def _entry(
    question: str, category: str | None, cost: float, in_tok: int, out_tok: int
) -> JournalEntry:
    return JournalEntry(
        question=question,
        artifact_type="sql",
        artifact="SELECT 1",
        status="accepted",
        model_id="m",
        input_tokens=in_tok,
        output_tokens=out_tok,
        estimated_cost_usd=cost,
        category=category,
    )


def test_load_journal_entries_returns_empty_for_missing_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert load_journal_entries(path=tmp_path / "nonexistent.jsonl") == []


def test_load_journal_entries_reads_all_lines(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "journal.jsonl"
    append_entry(_entry("Q1", "cat_a", 0.001, 100, 20), path=path)
    append_entry(_entry("Q2", "cat_a", 0.002, 200, 40), path=path)
    entries = load_journal_entries(path=path)
    assert len(entries) == 2


def test_aggregate_cost_by_category_groups_correctly(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "journal.jsonl"
    append_entry(_entry("Q1", "cat_a", 0.001, 100, 20), path=path)
    append_entry(_entry("Q2", "cat_a", 0.002, 200, 40), path=path)
    append_entry(_entry("Q3", "cat_b", 0.003, 500, 100), path=path)

    entries = load_journal_entries(path=path)
    report = aggregate_cost_by_category(entries)

    by_name = {c.category: c for c in report}
    assert by_name["cat_a"].question_count == 2
    assert by_name["cat_a"].total_cost_usd == 0.003
    assert by_name["cat_a"].total_input_tokens == 300
    assert by_name["cat_b"].question_count == 1


def test_aggregate_cost_avg_cost_per_question(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "journal.jsonl"
    append_entry(_entry("Q1", "cat_a", 0.002, 100, 20), path=path)
    append_entry(_entry("Q2", "cat_a", 0.004, 200, 40), path=path)

    report = aggregate_cost_by_category(load_journal_entries(path=path))
    assert report[0].avg_cost_usd == 0.003


def test_entries_without_category_are_uncategorized(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "journal.jsonl"
    append_entry(_entry("Q1", None, 0.001, 100, 20), path=path)

    report = aggregate_cost_by_category(load_journal_entries(path=path))
    assert report[0].category == "uncategorized"


def test_aggregate_cost_by_category_is_sorted() -> None:
    base = {"input_tokens": 1, "output_tokens": 1, "estimated_cost_usd": 0.1}
    entries = [
        {"question": "q1", "category": "zebra", **base},
        {"question": "q2", "category": "alpha", **base},
    ]
    report = aggregate_cost_by_category(entries)
    assert [c.category for c in report] == ["alpha", "zebra"]
