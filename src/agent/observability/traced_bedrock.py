"""Enveloppe `BedrockClient` pour tracer chaque appel dans Langfuse (modèle,
tokens, coût estimé) - traçabilité complète des appels Bedrock exigée en
Phase 6. Même interface que `BedrockClient.converse`, donc substituable
partout où un `BedrockClient` est attendu."""

from __future__ import annotations

from typing import Any

from agent.llm.bedrock_client import BedrockClient, ConverseResult, ToolConverseResult
from agent.observability.langfuse_client import get_langfuse_client
from agent.observability.pricing import estimate_cost
from config.settings import get_settings


class TracedBedrockClient:
    """`last_result` / `last_model_id` / `last_cost_usd` exposent les
    métriques du dernier appel : les générateurs (Phase 1-5) ne retournent
    que le texte extrait, donc un appelant qui a besoin des tokens/coût pour
    le journal d'audit (Phase 6) les relit ici après l'appel plutôt que de
    changer la signature de retour de chaque générateur."""

    def __init__(self, client: BedrockClient | None = None) -> None:
        self._client = client or BedrockClient()
        self._langfuse = get_langfuse_client()
        self.last_result: ConverseResult | None = None
        self.last_model_id: str | None = None
        self.last_cost_usd: float | None = None
        self.last_tool_result: ToolConverseResult | None = None

    def converse(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        model_id: str | None = None,
    ) -> ConverseResult:
        effective_model = model_id or get_settings().bedrock_model_id

        with self._langfuse.start_as_current_observation(
            name="bedrock-converse",
            as_type="generation",
            model=effective_model,
            input=messages,
            metadata={"system": system} if system else None,
        ) as generation:
            result = self._client.converse(
                messages=messages,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                model_id=model_id,
            )
            cost = estimate_cost(effective_model, result.input_tokens, result.output_tokens)
            generation.update(
                output=result.text,
                usage_details={"input": result.input_tokens, "output": result.output_tokens},
                cost_details={"total": cost} if cost is not None else None,
            )

        self.last_result = result
        self.last_model_id = effective_model
        self.last_cost_usd = cost
        return result

    def converse_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        model_id: str | None = None,
    ) -> ToolConverseResult:
        effective_model = model_id or get_settings().bedrock_model_id

        with self._langfuse.start_as_current_observation(
            name="bedrock-converse-with-tools",
            as_type="generation",
            model=effective_model,
            input=messages,
            metadata={"system": system} if system else None,
        ) as generation:
            result = self._client.converse_with_tools(
                messages=messages,
                tools=tools,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                model_id=model_id,
            )
            cost = estimate_cost(effective_model, result.input_tokens, result.output_tokens)
            generation.update(
                output=result.text,
                usage_details={"input": result.input_tokens, "output": result.output_tokens},
                cost_details={"total": cost} if cost is not None else None,
            )

        self.last_tool_result = result
        self.last_model_id = effective_model
        self.last_cost_usd = cost
        return result
