"""Client Langfuse partagé (traces, coûts Bedrock par requête — Phase 6)."""

from __future__ import annotations

from functools import lru_cache

from langfuse import Langfuse

from config.settings import get_settings


@lru_cache
def get_langfuse_client() -> Langfuse:
    settings = get_settings()
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
