"""Teste le rendu des artefacts d'outils (Phase 8) en éléments Chainlit et
la gestion du feedback. La construction d'éléments Chainlit nécessite un
contexte de session actif (thread_id) : on en installe un factice, comme le
ferait le serveur Chainlit en production."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
from chainlit.context import ChainlitContext, context_var
from chainlit.session import HTTPSession

from agent.orchestrator.state import ToolExecution

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))
import chainlit_app  # noqa: E402


@pytest.fixture(autouse=True)
def _fake_chainlit_context() -> None:
    async def _build() -> ChainlitContext:
        session = HTTPSession(id="test-session", client_type="webapp", thread_id="test-thread")
        return ChainlitContext(session=session)

    context_var.set(asyncio.run(_build()))


DF = pd.DataFrame({"category_name": ["Beverages", "Produce"], "n": [10, 5]})


def test_render_error_execution() -> None:
    execution = ToolExecution(llm_summary={"ok": False, "error": "Aucune donnée chargée."})

    message = chainlit_app._render_tool_execution(execution)

    assert message is not None
    assert "Aucune donnée chargée." in message.content


def test_render_query_data_execution() -> None:
    execution = ToolExecution(
        llm_summary={"ok": True, "row_count": 2},
        display={"sql": "SELECT 1", "dataframe": DF},
    )

    message = chainlit_app._render_tool_execution(execution)

    assert message is not None
    assert [type(e).__name__ for e in message.elements] == ["Text", "Dataframe"]
    assert message.elements[0].content == "SELECT 1"
    assert message.elements[1].data is DF


def test_render_compute_execution_with_dataframe() -> None:
    execution = ToolExecution(
        llm_summary={"ok": True},
        display={"code": "result = df", "result_dataframe": DF, "result_value": None},
    )

    message = chainlit_app._render_tool_execution(execution)

    assert message is not None
    assert [type(e).__name__ for e in message.elements] == ["Text", "Dataframe"]


def test_render_compute_execution_with_scalar() -> None:
    execution = ToolExecution(
        llm_summary={"ok": True, "result": 42},
        display={"code": "result = 42", "result_dataframe": None, "result_value": 42},
    )

    message = chainlit_app._render_tool_execution(execution)

    assert message is not None
    assert "42" in message.content


def test_render_visualize_execution() -> None:
    execution = ToolExecution(
        llm_summary={"ok": True, "commentary": "Le graphique montre..."},
        display={"chart_png": b"PNGDATA", "commentary": "Le graphique montre..."},
    )

    message = chainlit_app._render_tool_execution(execution)

    assert message is not None
    assert message.content == "Le graphique montre..."
    assert [type(e).__name__ for e in message.elements] == ["Image"]


def test_render_export_files_execution() -> None:
    execution = ToolExecution(
        llm_summary={"ok": True, "files": {"csv": "http://minio/x.csv"}},
        display={"files": {"csv": "http://minio/x.csv"}},
    )

    message = chainlit_app._render_tool_execution(execution)

    assert message is not None
    assert message.elements[0].url == "http://minio/x.csv"


def test_render_generate_report_execution() -> None:
    execution = ToolExecution(
        llm_summary={"ok": True, "narrative": "Analyse...", "report_url": "http://minio/r.pdf"},
        display={"narrative": "Analyse...", "url": "http://minio/r.pdf"},
    )

    message = chainlit_app._render_tool_execution(execution)

    assert message is not None
    assert message.content == "Analyse..."
    assert [type(e).__name__ for e in message.elements] == ["Pdf"]


def test_render_synthesize_reviews_execution() -> None:
    execution = ToolExecution(
        llm_summary={"ok": True, "synthesis": "Globalement positif."},
        display={"synthesis": "Globalement positif."},
    )

    message = chainlit_app._render_tool_execution(execution)

    assert message is not None
    assert message.content == "Globalement positif."


def test_feedback_helpful_saves_entry_and_removes_action(mocker) -> None:  # type: ignore[no-untyped-def]
    save_mock = mocker.patch.object(chainlit_app, "save_feedback")
    action = MagicMock()
    action.remove = mocker.AsyncMock()
    action.payload = {"question": "Combien de produits ?", "sql": "SELECT 1"}

    asyncio.run(chainlit_app.on_feedback_helpful(action))

    entry = save_mock.call_args.args[0]
    assert entry.question == "Combien de produits ?"
    assert entry.sql_executed == "SELECT 1"
    assert entry.rating == "helpful"
    action.remove.assert_called_once()


def test_feedback_not_helpful_saves_entry(mocker) -> None:  # type: ignore[no-untyped-def]
    save_mock = mocker.patch.object(chainlit_app, "save_feedback")
    action = MagicMock()
    action.remove = mocker.AsyncMock()
    action.payload = {"question": "q", "sql": ""}

    asyncio.run(chainlit_app.on_feedback_not_helpful(action))

    entry = save_mock.call_args.args[0]
    assert entry.rating == "not_helpful"
    assert entry.sql_executed is None
