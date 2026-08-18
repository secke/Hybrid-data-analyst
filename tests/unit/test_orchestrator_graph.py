"""Teste la structure et le routage du graphe LangGraph (Phase 8) : le
client Bedrock est mocké (simulateur de décisions - séquence de réponses
`converse_with_tools` scriptée), les outils exécutés sont mockés au niveau
`agent.orchestrator.tools` (déjà testés par ailleurs -
`test_orchestrator_tools.py`)."""

from __future__ import annotations

from unittest.mock import MagicMock

import agent.orchestrator.graph as graph_module
from agent.llm.bedrock_client import ToolUse
from agent.orchestrator.state import SessionState, ToolExecution


def _tool_use_result(name: str, tool_use_id: str, tool_input: dict[str, object]) -> MagicMock:
    call = ToolUse(tool_use_id=tool_use_id, name=name, input=tool_input)
    return MagicMock(
        content_blocks=[{"toolUse": {"toolUseId": tool_use_id, "name": name, "input": tool_input}}],
        text="",
        tool_calls=[call],
    )


def _text_result(text: str) -> MagicMock:
    return MagicMock(content_blocks=[{"text": text}], text=text, tool_calls=[])


def _fake_session() -> SessionState:
    return SessionState(bedrock_client=MagicMock())


def test_agent_answers_directly_without_tool_call() -> None:
    session = _fake_session()
    session.bedrock_client.converse_with_tools.return_value = _text_result("Bonjour !")
    ctx = MagicMock()

    final_state = graph_module.run_agent_turn(ctx, session, "Bonjour")

    assert final_state.final_text == "Bonjour !"
    assert final_state.iterations == 1
    assert final_state.tool_executions == []


def test_agent_calls_one_tool_then_answers(mocker) -> None:  # type: ignore[no-untyped-def]
    session = _fake_session()
    session.bedrock_client.converse_with_tools.side_effect = [
        _tool_use_result("query_data", "t1", {"question": "Combien de produits ?"}),
        _text_result("Voici la répartition."),
    ]
    fake_execution = ToolExecution(llm_summary={"ok": True, "row_count": 5})
    mocker.patch.object(
        graph_module,
        "TOOL_FUNCTIONS",
        {"query_data": lambda ctx, session, args: fake_execution},
    )
    ctx = MagicMock()

    final_state = graph_module.run_agent_turn(ctx, session, "Combien de produits ?")

    assert final_state.final_text == "Voici la répartition."
    assert final_state.iterations == 2
    assert final_state.tool_executions == [fake_execution]
    # Le message de résultat d'outil doit être injecté dans l'historique.
    tool_result_message = final_state.messages[-2]
    assert tool_result_message["role"] == "user"
    assert tool_result_message["content"][0]["toolResult"]["toolUseId"] == "t1"
    assert tool_result_message["content"][0]["toolResult"]["status"] == "success"


def test_failed_tool_execution_is_reported_as_error_status(mocker) -> None:  # type: ignore[no-untyped-def]
    session = _fake_session()
    session.bedrock_client.converse_with_tools.side_effect = [
        _tool_use_result("compute", "t1", {"question": "moyenne ?"}),
        _text_result("Je n'ai pas pu calculer."),
    ]
    failed_execution = ToolExecution(llm_summary={"ok": False, "error": "Aucune donnée chargée."})
    mocker.patch.object(
        graph_module,
        "TOOL_FUNCTIONS",
        {"compute": lambda ctx, session, args: failed_execution},
    )

    final_state = graph_module.run_agent_turn(MagicMock(), session, "moyenne ?")

    tool_result_message = final_state.messages[-2]
    assert tool_result_message["content"][0]["toolResult"]["status"] == "error"


def test_unknown_tool_name_does_not_crash_the_loop() -> None:
    session = _fake_session()
    session.bedrock_client.converse_with_tools.side_effect = [
        _tool_use_result("outil_inexistant", "t1", {}),
        _text_result("Je ne sais pas faire ça."),
    ]

    final_state = graph_module.run_agent_turn(MagicMock(), session, "fais un truc bizarre")

    assert final_state.final_text == "Je ne sais pas faire ça."
    tool_result_message = final_state.messages[-2]
    assert tool_result_message["content"][0]["toolResult"]["status"] == "error"


def test_tool_function_raising_is_caught_and_reported(mocker) -> None:  # type: ignore[no-untyped-def]
    session = _fake_session()
    session.bedrock_client.converse_with_tools.side_effect = [
        _tool_use_result("query_data", "t1", {"question": "q"}),
        _text_result("Une erreur est survenue."),
    ]

    def _boom(ctx: object, session: object, args: object) -> ToolExecution:
        raise RuntimeError("Postgres indisponible")

    mocker.patch.object(graph_module, "TOOL_FUNCTIONS", {"query_data": _boom})

    final_state = graph_module.run_agent_turn(MagicMock(), session, "q")

    assert final_state.tool_executions[0].llm_summary["ok"] is False
    assert "Postgres indisponible" in final_state.tool_executions[0].llm_summary["error"]


def test_loop_stops_at_max_tool_iterations() -> None:
    session = _fake_session()
    session.bedrock_client.converse_with_tools.side_effect = [
        _tool_use_result("synthesize_reviews", f"t{i}", {})
        for i in range(graph_module.MAX_TOOL_ITERATIONS + 3)
    ]

    final_state = graph_module.run_agent_turn(MagicMock(), session, "synthese des avis")

    assert final_state.iterations == graph_module.MAX_TOOL_ITERATIONS
    assert len(final_state.tool_executions) == graph_module.MAX_TOOL_ITERATIONS - 1
    assert session.bedrock_client.converse_with_tools.call_count == graph_module.MAX_TOOL_ITERATIONS


def test_history_from_previous_turn_is_prepended() -> None:
    session = _fake_session()
    session.bedrock_client.converse_with_tools.return_value = _text_result(
        "Suite de la conversation."
    )
    history = [
        {"role": "user", "content": [{"text": "Premier message"}]},
        {"role": "assistant", "content": [{"text": "Première réponse"}]},
    ]

    graph_module.run_agent_turn(MagicMock(), session, "Et ensuite ?", history=history)

    sent_messages = session.bedrock_client.converse_with_tools.call_args.kwargs["messages"]
    assert sent_messages[0] == history[0]
    assert sent_messages[1] == history[1]
    assert sent_messages[2]["content"][0]["text"] == "Et ensuite ?"
