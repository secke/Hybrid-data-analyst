"""Teste le traçage Langfuse des appels Bedrock contre le vrai Langfuse
local (docker-compose). Le client Bedrock sous-jacent est mocké - aucun
appel Bedrock réel."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from agent.observability.langfuse_client import get_langfuse_client
from agent.observability.traced_bedrock import TracedBedrockClient


def _langfuse_available() -> bool:
    try:
        return bool(get_langfuse_client().auth_check())
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _langfuse_available(), reason="Langfuse n'est pas disponible")


def test_traced_converse_returns_underlying_result() -> None:
    fake_inner = MagicMock()
    fake_inner.converse.return_value = MagicMock(
        text="Bonjour", input_tokens=50, output_tokens=10, stop_reason="end_turn"
    )
    traced = TracedBedrockClient(client=fake_inner)

    result = traced.converse(messages=[{"role": "user", "content": [{"text": "salut"}]}])

    assert result.text == "Bonjour"
    fake_inner.converse.assert_called_once()


def test_traced_converse_records_usage_and_model() -> None:
    fake_inner = MagicMock()
    fake_inner.converse.return_value = MagicMock(
        text="ok", input_tokens=42, output_tokens=7, stop_reason="end_turn"
    )
    traced = TracedBedrockClient(client=fake_inner)

    traced.converse(messages=[{"role": "user", "content": [{"text": "q"}]}])

    assert traced.last_result is not None
    assert traced.last_result.input_tokens == 42
    assert traced.last_model_id is not None
    assert traced.last_cost_usd is not None


def test_traced_converse_creates_a_real_langfuse_trace() -> None:
    import uuid

    marker = f"trace-verification-marker-{uuid.uuid4().hex}"
    fake_inner = MagicMock()
    fake_inner.converse.return_value = MagicMock(
        text=marker, input_tokens=33, output_tokens=11, stop_reason="end_turn"
    )
    traced = TracedBedrockClient(client=fake_inner)

    traced.converse(messages=[{"role": "user", "content": [{"text": "q"}]}])
    lf = get_langfuse_client()
    lf.flush()
    time.sleep(2)

    observations = lf.api.legacy.observations_v1.get_many(limit=20, name="bedrock-converse")
    matching = [o for o in observations.data if o.output == marker]
    assert len(matching) == 1
    assert matching[0].usage.input == 33
    assert matching[0].usage.output == 11
