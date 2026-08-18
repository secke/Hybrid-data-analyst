from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from agent.python_exec import pipeline as pipeline_module
from agent.python_exec.pipeline import answer_with_computation
from agent.sandbox.runner import SandboxResult

DF = pd.DataFrame({"category": ["A", "B"], "amount": [10, 20]})


def _fake_bedrock(*texts: str) -> MagicMock:
    client = MagicMock()
    client.converse.side_effect = [MagicMock(text=t) for t in texts]
    return client


def test_answer_with_computation_succeeds_on_first_attempt(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(
        pipeline_module, "run_code", return_value=SandboxResult(ok=True, result_value=30)
    )
    bedrock = _fake_bedrock("```python\nresult = df['amount'].sum()\n```")

    result = answer_with_computation("Somme ?", DF, bedrock_client=bedrock)

    assert result.ok
    assert result.result_value == 30
    assert len(result.attempts) == 1
    assert bedrock.converse.call_count == 1


def test_answer_with_computation_retries_after_execution_error(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(
        pipeline_module,
        "run_code",
        side_effect=[
            SandboxResult(ok=False, error="KeyError: 'amont'"),
            SandboxResult(ok=True, result_value=30),
        ],
    )
    bedrock = _fake_bedrock(
        "```python\nresult = df['amont'].sum()\n```",
        "```python\nresult = df['amount'].sum()\n```",
    )

    result = answer_with_computation("Somme ?", DF, bedrock_client=bedrock)

    assert result.ok
    assert len(result.attempts) == 2
    assert not result.attempts[0].execution.ok
    assert result.attempts[1].execution.ok

    second_call_kwargs = bedrock.converse.call_args_list[1].kwargs
    second_message = second_call_kwargs["messages"][0]["content"][0]["text"]
    assert "amont" in second_message


def test_answer_with_computation_fails_after_max_attempts(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(
        pipeline_module, "run_code", return_value=SandboxResult(ok=False, error="boom")
    )
    bedrock = _fake_bedrock(*(["```python\nresult = 1\n```"] * 3))

    result = answer_with_computation("Somme ?", DF, bedrock_client=bedrock, max_attempts=3)

    assert not result.ok
    assert result.code is None
    assert len(result.attempts) == 3
    assert bedrock.converse.call_count == 3


def test_answer_with_computation_returns_dataframe_result(mocker) -> None:  # type: ignore[no-untyped-def]
    output_df = pd.DataFrame({"category": ["A", "B"], "total": [10, 20]})
    mocker.patch.object(
        pipeline_module, "run_code", return_value=SandboxResult(ok=True, result_dataframe=output_df)
    )
    bedrock = _fake_bedrock("```python\nresult = df.groupby('category').sum()\n```")

    result = answer_with_computation("Somme par catégorie ?", DF, bedrock_client=bedrock)

    assert result.ok
    assert result.result_dataframe is not None
    assert result.result_dataframe.equals(output_df)
