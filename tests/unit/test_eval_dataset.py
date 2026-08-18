"""Valide le jeu de données d'évaluation Phase 7 : structure, et exécution
réelle de chaque SQL de référence contre Postgres (garde-fou de régression -
si une requête de référence casse, ce test le détecte immédiatement).
Aucun appel LLM."""

from __future__ import annotations

import json
from pathlib import Path

from agent.sql.executor import execute_readonly

EVAL_DATASET_PATH = (
    Path(__file__).resolve().parents[2] / "evaluation" / "eval_dataset.json"
)
ROBUSTNESS_DATASET_PATH = (
    Path(__file__).resolve().parents[2] / "evaluation" / "robustness_dataset.json"
)


def _load_eval_dataset() -> list[dict]:  # type: ignore[type-arg]
    result: list[dict] = json.loads(EVAL_DATASET_PATH.read_text(encoding="utf-8"))  # type: ignore[type-arg]
    return result


def _load_robustness_dataset() -> list[dict]:  # type: ignore[type-arg]
    result: list[dict] = json.loads(ROBUSTNESS_DATASET_PATH.read_text(encoding="utf-8"))  # type: ignore[type-arg]
    return result


def test_eval_dataset_has_50_questions() -> None:
    assert len(_load_eval_dataset()) == 50


def test_eval_dataset_ids_are_unique() -> None:
    dataset = _load_eval_dataset()
    ids = [item["id"] for item in dataset]
    assert len(ids) == len(set(ids))


def test_eval_dataset_entries_have_required_fields() -> None:
    for item in _load_eval_dataset():
        assert item["question"]
        assert item["category"]
        assert item["sql"]


def test_eval_dataset_has_multiple_categories() -> None:
    categories = {item["category"] for item in _load_eval_dataset()}
    assert len(categories) >= 5


def test_all_reference_sql_executes_successfully() -> None:
    failures = []
    for item in _load_eval_dataset():
        result = execute_readonly(item["sql"])
        if not result.ok:
            failures.append((item["id"], item["question"], result.error))
    assert not failures, f"Requêtes de référence en échec: {failures}"


def test_robustness_dataset_entries_have_required_fields() -> None:
    for item in _load_robustness_dataset():
        assert item["id"]
        assert item["category"]
        assert item["question"]
        assert item["note"]


def test_robustness_dataset_covers_expected_categories() -> None:
    categories = {item["category"] for item in _load_robustness_dataset()}
    assert {"nonexistent_column", "out_of_scope", "ambiguous"} <= categories
