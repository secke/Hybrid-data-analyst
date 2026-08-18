from __future__ import annotations

from unittest.mock import MagicMock

from agent.schema.introspect import ColumnInfo, TableSchema
from agent.schema.search import BM25SchemaIndex
from agent.sql import pipeline as pipeline_module
from agent.sql.executor import ExecutionResult
from agent.sql.pipeline import answer_question

ALLOWLIST = {"orders": {"order_id", "freight"}}
TABLES = [
    TableSchema(
        name="orders",
        columns=[ColumnInfo("order_id", "smallint", False), ColumnInfo("freight", "real", True)],
    )
]
TABLES_BY_NAME = {t.name: t for t in TABLES}


def _fake_bedrock(*texts: str) -> MagicMock:
    client = MagicMock()
    client.converse.side_effect = [MagicMock(text=t) for t in texts]
    return client


def _fake_qdrant_hit(table_name: str) -> MagicMock:
    hit = MagicMock()
    hit.payload = {"table_name": table_name}
    hit.score = 0.9
    return hit


def _fake_qdrant_client() -> MagicMock:
    client = MagicMock()
    client.query_points.return_value = MagicMock(points=[_fake_qdrant_hit("orders")])
    return client


def _fake_embedder() -> MagicMock:
    embedder = MagicMock()
    embedder.embed.return_value = MagicMock(vector=[0.1, 0.2, 0.3])
    return embedder


def _success_execution_result() -> ExecutionResult:
    return ExecutionResult(ok=True, columns=["order_id"], rows=[{"order_id": 1}], row_count=1)


def test_answer_question_succeeds_on_first_attempt(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(
        pipeline_module,
        "execute_readonly",
        return_value=_success_execution_result(),
    )
    bedrock = _fake_bedrock("```sql\nSELECT order_id FROM orders\n```")

    result = answer_question(
        "Combien de commandes ?",
        bedrock_client=bedrock,
        bm25_index=BM25SchemaIndex(TABLES),
        embedder=_fake_embedder(),
        qdrant_client=_fake_qdrant_client(),
        collection_name="schema_index",
        allowlist=ALLOWLIST,
        tables_by_name=TABLES_BY_NAME,
    )

    assert result.ok
    assert result.row_count == 1
    assert len(result.attempts) == 1
    assert bedrock.converse.call_count == 1


def test_answer_question_retries_after_validation_rejection(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(
        pipeline_module,
        "execute_readonly",
        return_value=_success_execution_result(),
    )
    bedrock = _fake_bedrock(
        "```sql\nSELECT * FROM unknown_table\n```",  # rejeté par le validateur
        "```sql\nSELECT order_id FROM orders\n```",  # correction acceptée
    )

    result = answer_question(
        "Combien de commandes ?",
        bedrock_client=bedrock,
        bm25_index=BM25SchemaIndex(TABLES),
        embedder=_fake_embedder(),
        qdrant_client=_fake_qdrant_client(),
        collection_name="schema_index",
        allowlist=ALLOWLIST,
        tables_by_name=TABLES_BY_NAME,
    )

    assert result.ok
    assert len(result.attempts) == 2
    assert not result.attempts[0].validation.ok
    assert result.attempts[1].validation.ok
    # la deuxième tentative doit avoir reçu l'erreur de la première
    second_call_kwargs = bedrock.converse.call_args_list[1].kwargs
    second_call_message = second_call_kwargs["messages"][0]["content"][0]["text"]
    assert "unknown_table" in second_call_message or "inconnue" in second_call_message.lower()


def test_answer_question_retries_after_execution_error(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(
        pipeline_module,
        "execute_readonly",
        side_effect=[
            ExecutionResult(ok=False, error="division by zero"),
            ExecutionResult(ok=True, columns=["order_id"], rows=[{"order_id": 1}], row_count=1),
        ],
    )
    bedrock = _fake_bedrock(
        "```sql\nSELECT order_id FROM orders\n```",
        "```sql\nSELECT order_id FROM orders\n```",
    )

    result = answer_question(
        "Combien de commandes ?",
        bedrock_client=bedrock,
        bm25_index=BM25SchemaIndex(TABLES),
        embedder=_fake_embedder(),
        qdrant_client=_fake_qdrant_client(),
        collection_name="schema_index",
        allowlist=ALLOWLIST,
        tables_by_name=TABLES_BY_NAME,
    )

    assert result.ok
    assert len(result.attempts) == 2
    assert result.attempts[0].execution is not None
    assert not result.attempts[0].execution.ok


def test_answer_question_fails_after_max_attempts(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(pipeline_module, "execute_readonly")
    bedrock = _fake_bedrock(*(["```sql\nSELECT * FROM unknown_table\n```"] * 3))

    result = answer_question(
        "Combien de commandes ?",
        bedrock_client=bedrock,
        bm25_index=BM25SchemaIndex(TABLES),
        embedder=_fake_embedder(),
        qdrant_client=_fake_qdrant_client(),
        collection_name="schema_index",
        allowlist=ALLOWLIST,
        tables_by_name=TABLES_BY_NAME,
        max_attempts=3,
    )

    assert not result.ok
    assert result.sql is None
    assert len(result.attempts) == 3
    assert bedrock.converse.call_count == 3
