"""Tarification Bedrock par modèle, pour le suivi de coût (Phase 6).

Prix en dollars par million de tokens, vérifiés au 2026-08 (pricing on-demand
Bedrock us-*, cf. README pour les sources). Un modèle absent de cette table
n'a pas son coût inventé : `estimate_cost` retourne `None` plutôt qu'un
chiffre approximatif - conforme au principe "dire je ne sais pas plutôt que
d'inventer"."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    input_per_million: float
    output_per_million: float


PRICING_PER_MILLION_TOKENS: dict[str, ModelPricing] = {
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0": ModelPricing(3.00, 15.00),
    "global.anthropic.claude-sonnet-4-5-20250929-v1:0": ModelPricing(3.00, 15.00),
    "us.anthropic.claude-sonnet-5": ModelPricing(3.00, 15.00),
    "global.anthropic.claude-sonnet-5": ModelPricing(3.00, 15.00),
    "amazon.titan-embed-text-v2:0": ModelPricing(0.02, 0.0),
}


def estimate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float | None:
    """Retourne `None` (jamais un chiffre inventé) si le modèle n'est pas
    dans `PRICING_PER_MILLION_TOKENS`."""
    pricing = PRICING_PER_MILLION_TOKENS.get(model_id)
    if pricing is None:
        return None
    return (
        input_tokens * pricing.input_per_million / 1_000_000
        + output_tokens * pricing.output_per_million / 1_000_000
    )
