"""Protocoles structurels pour découpler le code d'indexation/recherche/
génération du client Bedrock concret - permet de les tester avec un client
factice (ou une enveloppe comme `TracedBedrockClient`, Phase 6), sans appel
réseau."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from agent.llm.bedrock_client import ConverseResult


class EmbeddingLike(Protocol):
    @property
    def vector(self) -> list[float]: ...


class Embedder(Protocol):
    def embed(self, text: str, dimensions: int = ...) -> EmbeddingLike: ...


class BedrockConverser(Protocol):
    """Satisfait par `BedrockClient` et par `TracedBedrockClient` (Phase 6)."""

    def converse(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        max_tokens: int = ...,
        temperature: float = ...,
        model_id: str | None = None,
    ) -> ConverseResult: ...
