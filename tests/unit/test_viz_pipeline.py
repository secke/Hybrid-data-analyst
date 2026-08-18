from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from agent.sandbox.runner import SandboxResult
from agent.viz import pipeline as pipeline_module
from agent.viz.pipeline import generate_chart

DF = pd.DataFrame({"category": ["A", "B"], "amount": [10, 20]})
PNG_BYTES = b"\x89PNG\r\n\x1a\nfake"
HTML = "<html>chart</html>"


def _fake_bedrock(*texts: str) -> MagicMock:
    client = MagicMock()
    client.converse.side_effect = [MagicMock(text=t) for t in texts]
    return client


def test_generate_chart_succeeds_on_first_attempt(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(
        pipeline_module,
        "run_code",
        return_value=SandboxResult(ok=True, chart_png_bytes=PNG_BYTES, chart_html=HTML),
    )
    bedrock = _fake_bedrock("```python\nfig = px.bar(df, x='category', y='amount')\n```")

    result = generate_chart("Graphique ?", DF, bedrock_client=bedrock)

    assert result.ok
    assert result.chart_png_bytes == PNG_BYTES
    assert result.chart_html == HTML
    assert len(result.attempts) == 1


def test_generate_chart_retries_when_fig_is_missing(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(
        pipeline_module,
        "run_code",
        side_effect=[
            SandboxResult(ok=True, result_value=42),  # code valide mais sans `fig`
            SandboxResult(ok=True, chart_png_bytes=PNG_BYTES, chart_html=HTML),
        ],
    )
    bedrock = _fake_bedrock(
        "```python\nresult = df['amount'].sum()\n```",
        "```python\nfig = px.bar(df, x='category', y='amount')\n```",
    )

    result = generate_chart("Graphique ?", DF, bedrock_client=bedrock)

    assert result.ok
    assert len(result.attempts) == 2
    assert result.attempts[0].execution.chart_png_bytes is None

    second_call_kwargs = bedrock.converse.call_args_list[1].kwargs
    second_message = second_call_kwargs["messages"][0]["content"][0]["text"]
    assert "fig" in second_message.lower()


def test_generate_chart_retries_after_execution_error(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(
        pipeline_module,
        "run_code",
        side_effect=[
            SandboxResult(ok=False, error="KeyError: 'foo'"),
            SandboxResult(ok=True, chart_png_bytes=PNG_BYTES, chart_html=HTML),
        ],
    )
    bedrock = _fake_bedrock(
        "```python\nfig = px.bar(df, x='foo', y='amount')\n```",
        "```python\nfig = px.bar(df, x='category', y='amount')\n```",
    )

    result = generate_chart("Graphique ?", DF, bedrock_client=bedrock)

    assert result.ok
    assert len(result.attempts) == 2


def test_generate_chart_fails_after_max_attempts(mocker) -> None:  # type: ignore[no-untyped-def]
    failing_result = SandboxResult(ok=False, error="boom")
    mocker.patch.object(pipeline_module, "run_code", return_value=failing_result)
    bedrock = _fake_bedrock(*(["```python\nfig = None\n```"] * 3))

    result = generate_chart("Graphique ?", DF, bedrock_client=bedrock, max_attempts=3)

    assert not result.ok
    assert result.chart_png_bytes is None
    assert len(result.attempts) == 3
