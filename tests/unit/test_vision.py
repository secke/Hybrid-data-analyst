from __future__ import annotations

from unittest.mock import MagicMock

from agent.viz.vision import build_vision_messages, comment_on_chart

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png-bytes"


def test_build_vision_messages_includes_image_block() -> None:
    messages = build_vision_messages("Question ?", PNG_BYTES)
    content = messages[0]["content"]
    image_blocks = [b for b in content if "image" in b]
    assert len(image_blocks) == 1
    assert image_blocks[0]["image"]["format"] == "png"
    assert image_blocks[0]["image"]["source"]["bytes"] == PNG_BYTES


def test_build_vision_messages_includes_question_text() -> None:
    messages = build_vision_messages("Évolution des ventes ?", PNG_BYTES)
    content = messages[0]["content"]
    text_blocks = [b["text"] for b in content if "text" in b]
    assert any("Évolution des ventes ?" in t for t in text_blocks)


def test_comment_on_chart_calls_bedrock_with_image_and_strips_response() -> None:
    fake_client = MagicMock()
    fake_client.converse.return_value = MagicMock(text="  Tendance à la hausse.  ")

    comment = comment_on_chart("Question ?", PNG_BYTES, fake_client)

    assert comment == "Tendance à la hausse."
    fake_client.converse.assert_called_once()
    _, kwargs = fake_client.converse.call_args
    assert "UNIQUEMENT" in kwargs["system"]
    image_blocks = [b for b in kwargs["messages"][0]["content"] if "image" in b]
    assert image_blocks[0]["image"]["source"]["bytes"] == PNG_BYTES
