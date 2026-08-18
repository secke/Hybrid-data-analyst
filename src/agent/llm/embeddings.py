"""Wrapper autour de Titan Embeddings v2 (amazon.titan-embed-text-v2:0), utilisé
pour indexer le schéma de la base dans Qdrant (Phase 1)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from config.settings import Settings, get_settings

from .retry import is_retryable_bedrock_error

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    input_tokens: int


class TitanEmbeddingsClient:
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
                retries={"max_attempts": 0},
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
    def embed(self, text: str, dimensions: int = 1024) -> EmbeddingResult:
        body = json.dumps({"inputText": text, "dimensions": dimensions, "normalize": True})
        try:
            response = self._client.invoke_model(
                modelId=self._settings.bedrock_embedding_model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
        except ClientError:
            logger.exception("Appel Bedrock embed() échoué")
            raise

        payload = json.loads(response["body"].read())
        return EmbeddingResult(
            vector=payload["embedding"],
            input_tokens=payload["inputTextTokenCount"],
        )
