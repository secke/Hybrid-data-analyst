from __future__ import annotations

from unittest.mock import MagicMock

from agent.federation import pipeline as pipeline_module
from agent.federation.pipeline import answer_federated_question
from agent.schema.introspect import ColumnInfo, TableSchema
from agent.sql.executor import ExecutionResult

ALLOWLIST = {"orders": {"order_id", "ship_country"}, "online_retail": {"country"}}
TABLES = [
    TableSchema(name="orders", columns=[ColumnInfo("order_id", "smallint", False)]),
    TableSchema(name="online_retail", columns=[ColumnInfo("country", "varchar", True)]),
]


def _fake_bedrock(*texts: str) -> MagicMock:
    client = MagicMock()
    client.converse.side_effect = [MagicMock(text=t) for t in texts]
    return client


def _success_execution_result() -> ExecutionResult:
    return ExecutionResult(ok=True, columns=["order_id"], rows=[{"order_id": 1}], row_count=1)


def test_answer_federated_question_succeeds_on_first_attempt(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(
        pipeline_module,
        "execute_federated",
        return_value=_success_execution_result(),
    )
    bedrock = _fake_bedrock("```sql\nSELECT order_id FROM orders\n```")

    result = answer_federated_question(
        "q", con=MagicMock(), bedrock_client=bedrock, tables=TABLES, allowlist=ALLOWLIST
    )

    assert result.ok
    assert result.row_count == 1
    assert len(result.attempts) == 1


def test_answer_federated_question_retries_after_rejection(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(
        pipeline_module,
        "execute_federated",
        return_value=_success_execution_result(),
    )
    bedrock = _fake_bedrock(
        "```sql\nSELECT * FROM secret_table\n```",
        "```sql\nSELECT order_id FROM orders\n```",
    )

    result = answer_federated_question(
        "q", con=MagicMock(), bedrock_client=bedrock, tables=TABLES, allowlist=ALLOWLIST
    )

    assert result.ok
    assert len(result.attempts) == 2
    assert not result.attempts[0].validation.ok


def test_answer_federated_question_fails_after_max_attempts(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(pipeline_module, "execute_federated")
    bedrock = _fake_bedrock(*(["```sql\nSELECT * FROM secret_table\n```"] * 3))

    result = answer_federated_question(
        "q",
        con=MagicMock(),
        bedrock_client=bedrock,
        tables=TABLES,
        allowlist=ALLOWLIST,
        max_attempts=3,
    )

    assert not result.ok
    assert result.sql is None
    assert len(result.attempts) == 3


def test_answer_federated_question_passes_extra_context_to_generator(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(
        pipeline_module,
        "execute_federated",
        return_value=_success_execution_result(),
    )
    bedrock = _fake_bedrock("```sql\nSELECT order_id FROM orders\n```")

    answer_federated_question(
        "q",
        con=MagicMock(),
        bedrock_client=bedrock,
        tables=TABLES,
        allowlist=ALLOWLIST,
        extra_context="1 GBP = 1.36 USD",
    )

    _, kwargs = bedrock.converse.call_args
    user_message = kwargs["messages"][0]["content"][0]["text"]
    assert "1 GBP = 1.36 USD" in user_message
