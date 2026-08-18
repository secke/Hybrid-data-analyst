"""Teste la base de feedback contre le vrai Postgres local. Aucun appel
LLM."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from agent.db.postgres import get_app_engine
from agent.feedback.store import FeedbackEntry, get_validated_queries, save_feedback


@pytest.fixture(autouse=True)
def _cleanup_feedback():  # type: ignore[no-untyped-def]
    yield
    engine = get_app_engine()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM agent_feedback WHERE identity = 'pytest'"))


def _feedback(question: str, rating: str = "helpful", **overrides: object) -> FeedbackEntry:
    defaults: dict[str, object] = {
        "question": question,
        "sql_executed": "SELECT 1",
        "rating": rating,
        "identity": "pytest",
    }
    defaults.update(overrides)
    return FeedbackEntry(**defaults)  # type: ignore[arg-type]


def test_save_feedback_returns_an_id() -> None:
    feedback_id = save_feedback(_feedback("Q1"))
    assert isinstance(feedback_id, int)


def test_get_validated_queries_only_returns_helpful() -> None:
    save_feedback(_feedback("Helpful Q", rating="helpful"))
    save_feedback(_feedback("Not helpful Q", rating="not_helpful"))

    validated = get_validated_queries()
    questions = {row["question"] for row in validated}
    assert "Helpful Q" in questions
    assert "Not helpful Q" not in questions


def test_get_validated_queries_most_recent_first() -> None:
    save_feedback(_feedback("First"))
    save_feedback(_feedback("Second"))

    validated = get_validated_queries(limit=2)
    pytest_rows = [r for r in validated if r["identity"] == "pytest"]
    assert pytest_rows[0]["question"] == "Second"


def test_save_feedback_stores_comment() -> None:
    save_feedback(_feedback("Q", comment="Très utile"))
    validated = get_validated_queries()
    matching = [r for r in validated if r["question"] == "Q" and r["identity"] == "pytest"]
    assert matching[0]["comment"] == "Très utile"
