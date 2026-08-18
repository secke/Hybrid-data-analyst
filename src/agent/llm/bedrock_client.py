"""Wrapper fin autour de bedrock-runtime pour la génération (Claude, API Converse).

L'API Converse accepte aussi bien du texte que des blocs image (vision, Phase 3),
donc ce même client sert les deux usages.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from config.settings import Settings, get_settings

from .retry import is_retryable_bedrock_error

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConverseResult:
    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str


@dataclass(frozen=True)
class ToolUse:
    tool_use_id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class ToolConverseResult:
    """Résultat d'un appel Converse avec `toolConfig` (agent à outils,
    orchestrateur LangGraph). `content_blocks` préserve les blocs bruts
    (texte + toolUse) dans leur ordre d'origine - nécessaire pour reconstruire
    le message assistant complet dans l'historique de conversation."""

    content_blocks: list[dict[str, Any]]
    input_tokens: int
    output_tokens: int
    stop_reason: str

    @property
    def text(self) -> str:
        return "".join(block.get("text", "") for block in self.content_blocks)

    @property
    def tool_calls(self) -> list[ToolUse]:
        return [
            ToolUse(
                tool_use_id=block["toolUse"]["toolUseId"],
                name=block["toolUse"]["name"],
                input=block["toolUse"]["input"],
            )
            for block in self.content_blocks
            if "toolUse" in block
        ]


class BedrockClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        session = (
            boto3.Session(profile_name=self._settings.aws_profile)
            if self._settings.aws_profile
            else boto3.Session()
        )
        self._client = session.client(
            "bedrock-runtime",
            region_name=self._settings.aws_region,
            config=Config(
                retries={"max_attempts": 0},  # retries gérés explicitement ci-dessous (tenacity)
                read_timeout=self._settings.bedrock_timeout_seconds,
                connect_timeout=10,
            ),
        )

    @retry(
        retry=retry_if_exception(is_retryable_bedrock_error),
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=20),
        reraise=True,
    )
    def converse(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        model_id: str | None = None,
    ) -> ConverseResult:
        kwargs: dict[str, Any] = {
            "modelId": model_id or self._settings.bedrock_model_id,
            "messages": messages,
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
        }
        if system:
            kwargs["system"] = [{"text": system}]

        try:
            response = self._client.converse(**kwargs)
        except ClientError:
            logger.exception("Appel Bedrock converse() échoué")
            raise

        output_message = response["output"]["message"]
        text = "".join(block.get("text", "") for block in output_message["content"])
        usage = response["usage"]

        return ConverseResult(
            text=text,
            input_tokens=usage["inputTokens"],
            output_tokens=usage["outputTokens"],
            stop_reason=response["stopReason"],
        )

    @retry(
        retry=retry_if_exception(is_retryable_bedrock_error),
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=20),
        reraise=True,
    )
    def converse_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        model_id: str | None = None,
    ) -> ToolConverseResult:
        """`tools` : liste de spécifications au format Bedrock Converse
        (`[{"toolSpec": {"name", "description", "inputSchema": {"json": <JSON Schema>}}}, ...]`).
        Utilisé par l'orchestrateur (agent à outils, LangGraph) pour décider
        quel pipeline appeler - jamais par les générateurs simples
        (SQL/Python/viz/rapport), qui utilisent `converse()`."""
        kwargs: dict[str, Any] = {
            "modelId": model_id or self._settings.bedrock_model_id,
            "messages": messages,
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
            "toolConfig": {"tools": tools},
        }
        if system:
            kwargs["system"] = [{"text": system}]

        try:
            response = self._client.converse(**kwargs)
        except ClientError:
            logger.exception("Appel Bedrock converse_with_tools() échoué")
            raise

        output_message = response["output"]["message"]
        usage = response["usage"]

        return ToolConverseResult(
            content_blocks=output_message["content"],
            input_tokens=usage["inputTokens"],
            output_tokens=usage["outputTokens"],
            stop_reason=response["stopReason"],
        )
