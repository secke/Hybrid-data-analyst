"""Base de feedback utilisateur (Phase 6) : stocke une note (utile / pas
utile) sur chaque question/SQL répondue par le pipeline, pour constituer une
base de requêtes validées réutilisable (Phase 7 : jeu d'évaluation ;
Phase 1+ : exemples few-shot potentiels).

Utilise le rôle applicatif (agent_app) : ce sont des données de contrôle
internes à l'application, pas des données analytiques exposées au SQL généré
par le LLM (qui reste cantonné au rôle agent_readonly, cf. Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from agent.db.postgres import get_app_engine

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agent_feedback (
    id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    sql_executed TEXT,
    rating TEXT NOT NULL CHECK (rating IN ('helpful', 'not_helpful')),
    comment TEXT,
    identity TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def ensure_feedback_table() -> None:
    engine = get_app_engine()
    with engine.begin() as conn:
        conn.execute(text(_CREATE_TABLE_SQL))


@dataclass(frozen=True)
class FeedbackEntry:
    question: str
    sql_executed: str | None
    rating: str  # "helpful" | "not_helpful"
    identity: str
    comment: str | None = None


def save_feedback(entry: FeedbackEntry) -> int:
    ensure_feedback_table()
    engine = get_app_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO agent_feedback (question, sql_executed, rating, comment, identity) "
                "VALUES (:question, :sql_executed, :rating, :comment, :identity) RETURNING id"
            ),
            {
                "question": entry.question,
                "sql_executed": entry.sql_executed,
                "rating": entry.rating,
                "comment": entry.comment,
                "identity": entry.identity,
            },
        )
        feedback_id: int = result.scalar_one()
    return feedback_id


def get_validated_queries(limit: int = 100) -> list[dict[str, object]]:
    """Requêtes marquées `helpful`, les plus récentes d'abord - base pour de
    futurs exemples few-shot ou un jeu d'évaluation (Phase 7)."""
    ensure_feedback_table()
    engine = get_app_engine()
    with engine.connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT question, sql_executed, comment, identity, created_at "
                    "FROM agent_feedback WHERE rating = 'helpful' "
                    "ORDER BY created_at DESC LIMIT :limit"
                ),
                {"limit": limit},
            )
            .mappings()
            .all()
        )
    return [dict(row) for row in rows]
