from __future__ import annotations

import pytest

from agent.observability.pricing import estimate_cost


def test_estimate_cost_known_model() -> None:
    cost = estimate_cost("us.anthropic.claude-sonnet-4-5-20250929-v1:0", 1000, 200)
    assert cost == pytest.approx(1000 * 3.00 / 1_000_000 + 200 * 15.00 / 1_000_000)


def test_estimate_cost_titan_embeddings_has_no_output_cost() -> None:
    cost = estimate_cost("amazon.titan-embed-text-v2:0", 1000, 0)
    assert cost == pytest.approx(1000 * 0.02 / 1_000_000)


def test_estimate_cost_unknown_model_returns_none() -> None:
    assert estimate_cost("some-unknown-model", 100, 50) is None


def test_estimate_cost_zero_tokens_is_zero() -> None:
    assert estimate_cost("us.anthropic.claude-sonnet-4-5-20250929-v1:0", 0, 0) == 0.0
