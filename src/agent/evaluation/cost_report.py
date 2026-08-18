"""Agrégation du coût Bedrock par catégorie de question (Phase 7), à partir
du journal d'audit immuable (Phase 6, champ `category`) - pour le business
case entreprise. Entièrement déterministe : lit des entrées déjà
journalisées, n'appelle jamais Bedrock."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.audit.journal import JOURNAL_PATH


@dataclass(frozen=True)
class CategoryCost:
    category: str
    question_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float

    @property
    def avg_cost_usd(self) -> float:
        return self.total_cost_usd / self.question_count if self.question_count else 0.0


def load_journal_entries(path: Path = JOURNAL_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))
    return entries


def aggregate_cost_by_category(entries: list[dict[str, Any]]) -> list[CategoryCost]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        category = entry.get("category") or "uncategorized"
        grouped[category].append(entry)

    results = [
        CategoryCost(
            category=category,
            question_count=len(group),
            total_input_tokens=sum(e.get("input_tokens", 0) for e in group),
            total_output_tokens=sum(e.get("output_tokens", 0) for e in group),
            total_cost_usd=sum(e.get("estimated_cost_usd", 0.0) for e in group),
        )
        for category, group in grouped.items()
    ]
    return sorted(results, key=lambda c: c.category)
