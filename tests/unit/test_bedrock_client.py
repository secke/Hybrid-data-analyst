from __future__ import annotations

from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from agent.llm.bedrock_client import BedrockClient
from agent.llm.retry import is_retryable_bedrock_error
from config.settings import Settings


def _throttling_error() -> ClientError:
    return ClientError(
        error_response={"Error": {"Code": "ThrottlingException", "Message": "slow down"}},
        operation_name="Converse",
    )


def _access_denied_error() -> ClientError:
    return ClientError(
        error_response={"Error": {"Code": "AccessDeniedException", "Message": "nope"}},
        operation_name="Converse",
    )


def test_is_retryable_bedrock_error_true_for_throttling() -> None:
    assert is_retryable_bedrock_error(_throttling_error()) is True


def test_is_retryable_bedrock_error_false_for_access_denied() -> None:
    assert is_retryable_bedrock_error(_access_denied_error()) is False


def test_is_retryable_bedrock_error_false_for_non_client_error() -> None:
    assert is_retryable_bedrock_error(ValueError("boom")) is False


def test_converse_parses_response(mocker) -> None:  # type: ignore[no-untyped-def]
    mock_boto_client = MagicMock()
    mock_boto_client.converse.return_value = {
        "output": {"message": {"role": "assistant", "content": [{"text": "Bonjour"}]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 10, "outputTokens": 3},
    }
    mocker.patch("boto3.Session.client", return_value=mock_boto_client)

    client = BedrockClient(settings=Settings(aws_region="us-west-2", aws_profile=None))
    result = client.converse(messages=[{"role": "user", "content": [{"text": "Salut"}]}])

    assert result.text == "Bonjour"
    assert result.input_tokens == 10
    assert result.output_tokens == 3
    assert result.stop_reason == "end_turn"
    mock_boto_client.converse.assert_called_once()


def test_converse_retries_on_throttling_then_succeeds(mocker) -> None:  # type: ignore[no-untyped-def]
    mock_boto_client = MagicMock()
    mock_boto_client.converse.side_effect = [
        _throttling_error(),
        {
            "output": {"message": {"role": "assistant", "content": [{"text": "OK"}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 5, "outputTokens": 1},
        },
    ]
    mocker.patch("boto3.Session.client", return_value=mock_boto_client)
    mocker.patch("time.sleep", return_value=None)  # n'attend pas réellement entre les tentatives

    client = BedrockClient(settings=Settings(aws_region="us-west-2", aws_profile=None))
    result = client.converse(messages=[{"role": "user", "content": [{"text": "Salut"}]}])

    assert result.text == "OK"
    assert mock_boto_client.converse.call_count == 2


def test_converse_does_not_retry_on_non_retryable_error(mocker) -> None:  # type: ignore[no-untyped-def]
    mock_boto_client = MagicMock()
    mock_boto_client.converse.side_effect = _access_denied_error()
    mocker.patch("boto3.Session.client", return_value=mock_boto_client)

    client = BedrockClient(settings=Settings(aws_region="us-west-2", aws_profile=None))
    try:
        client.converse(messages=[{"role": "user", "content": [{"text": "Salut"}]}])
    except ClientError:
        pass
    else:
        raise AssertionError("Une ClientError non retryable aurait dû être propagée")

    assert mock_boto_client.converse.call_count == 1


def _tool_spec(name: str) -> dict:  # type: ignore[type-arg]
    return {
        "toolSpec": {
            "name": name,
            "description": "desc",
            "inputSchema": {"json": {"type": "object", "properties": {}}},
        }
    }


def test_converse_with_tools_sends_tool_config(mocker) -> None:  # type: ignore[no-untyped-def]
    mock_boto_client = MagicMock()
    mock_boto_client.converse.return_value = {
        "output": {"message": {"role": "assistant", "content": [{"text": "OK"}]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 10, "outputTokens": 2},
    }
    mocker.patch("boto3.Session.client", return_value=mock_boto_client)

    client = BedrockClient(settings=Settings(aws_region="us-west-2", aws_profile=None))
    tools = [_tool_spec("query_data")]
    client.converse_with_tools(messages=[{"role": "user", "content": [{"text": "q"}]}], tools=tools)

    sent_kwargs = mock_boto_client.converse.call_args.kwargs
    assert sent_kwargs["toolConfig"] == {"tools": tools}


def test_converse_with_tools_parses_tool_use_block(mocker) -> None:  # type: ignore[no-untyped-def]
    mock_boto_client = MagicMock()
    mock_boto_client.converse.return_value = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {"text": "Je vais chercher."},
                    {
                        "toolUse": {
                            "toolUseId": "tu_1",
                            "name": "query_data",
                            "input": {"question": "CA total ?"},
                        }
                    },
                ],
            }
        },
        "stopReason": "tool_use",
        "usage": {"inputTokens": 200, "outputTokens": 50},
    }
    mocker.patch("boto3.Session.client", return_value=mock_boto_client)

    client = BedrockClient(settings=Settings(aws_region="us-west-2", aws_profile=None))
    result = client.converse_with_tools(
        messages=[{"role": "user", "content": [{"text": "q"}]}], tools=[_tool_spec("query_data")]
    )

    assert result.text == "Je vais chercher."
    assert result.stop_reason == "tool_use"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "query_data"
    assert result.tool_calls[0].input == {"question": "CA total ?"}
    assert result.tool_calls[0].tool_use_id == "tu_1"


def test_converse_with_tools_no_tool_call_returns_empty_list(mocker) -> None:  # type: ignore[no-untyped-def]
    mock_boto_client = MagicMock()
    mock_boto_client.converse.return_value = {
        "output": {"message": {"role": "assistant", "content": [{"text": "Reponse finale."}]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 100, "outputTokens": 20},
    }
    mocker.patch("boto3.Session.client", return_value=mock_boto_client)

    client = BedrockClient(settings=Settings(aws_region="us-west-2", aws_profile=None))
    result = client.converse_with_tools(
        messages=[{"role": "user", "content": [{"text": "q"}]}], tools=[_tool_spec("query_data")]
    )

    assert result.tool_calls == []
    assert result.text == "Reponse finale."


def test_converse_with_tools_preserves_raw_content_blocks(mocker) -> None:  # type: ignore[no-untyped-def]
    mock_boto_client = MagicMock()
    content = [{"text": "a"}, {"toolUse": {"toolUseId": "x", "name": "n", "input": {}}}]
    mock_boto_client.converse.return_value = {
        "output": {"message": {"role": "assistant", "content": content}},
        "stopReason": "tool_use",
        "usage": {"inputTokens": 1, "outputTokens": 1},
    }
    mocker.patch("boto3.Session.client", return_value=mock_boto_client)

    client = BedrockClient(settings=Settings(aws_region="us-west-2", aws_profile=None))
    result = client.converse_with_tools(
        messages=[{"role": "user", "content": [{"text": "q"}]}], tools=[_tool_spec("n")]
    )

    assert result.content_blocks == content
