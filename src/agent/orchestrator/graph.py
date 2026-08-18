"""Graphe LangGraph (Phase 8) : agent qui décide seul, via l'API Bedrock
Converse en mode `toolConfig`, quel(s) outil(s) invoquer pour répondre à la
question de l'utilisateur (`agent.orchestrator.tools`). Boucle agent -> outils
-> agent jusqu'à ce que le modèle réponde sans demander de nouvel outil, avec
une limite de tentatives pour éviter toute boucle infinie en cas de
comportement inattendu du modèle."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from langgraph.graph import END, StateGraph

from agent.llm.bedrock_client import ToolUse
from agent.orchestrator.context import ToolContext
from agent.orchestrator.state import SessionState, ToolExecution
from agent.orchestrator.tools import (
    TOOL_SPECS,
    tool_compute,
    tool_export_files,
    tool_generate_report,
    tool_query_data,
    tool_query_federated_data,
    tool_synthesize_reviews,
    tool_visualize,
)

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 8

SYSTEM_PROMPT = """Tu es un agent d'analyse de données pour une entreprise qui \
combine une base ERP/CRM (Northwind) et un export e-commerce réel (Online \
Retail II). Tu réponds aux questions de l'utilisateur en choisissant et \
enchaînant les outils appropriés :
- `query_data` : questions portant uniquement sur Northwind.
- `query_federated_data` : questions combinant Northwind et Online Retail II.
- `compute` : calcul Python sur les données déjà récupérées (nécessite un \
appel préalable à query_data ou query_federated_data dans cette conversation).
- `visualize` : graphique sur les données déjà récupérées (même prérequis).
- `export_files` : export Excel/CSV/PDF des données déjà récupérées (même \
prérequis).
- `generate_report` : rapport narratif PDF traçable sur les données déjà \
récupérées (même prérequis).
- `synthesize_reviews` : synthèse qualitative d'avis clients Amazon, sans \
prérequis.

Règles impératives :
- N'appelle jamais compute/visualize/export_files/generate_report avant \
d'avoir récupéré des données dans cette conversation via query_data ou \
query_federated_data.
- Une fois les outils nécessaires exécutés, réponds à l'utilisateur en \
langage naturel, de façon concise, en te basant strictement sur les résultats \
d'outils obtenus (jamais de chiffre inventé).
- Si un outil échoue, explique le problème à l'utilisateur plutôt que de \
réessayer indéfiniment le même outil avec les mêmes arguments."""

TOOL_FUNCTIONS: dict[str, Any] = {
    "query_data": lambda ctx, session, args: tool_query_data(ctx, session, args["question"]),
    "query_federated_data": (
        lambda ctx, session, args: tool_query_federated_data(ctx, session, args["question"])
    ),
    "compute": lambda ctx, session, args: tool_compute(ctx, session, args["question"]),
    "visualize": lambda ctx, session, args: tool_visualize(ctx, session, args["question"]),
    "export_files": lambda ctx, session, args: tool_export_files(ctx, session, args["formats"]),
    "generate_report": (
        lambda ctx, session, args: tool_generate_report(ctx, session, args["question"])
    ),
    "synthesize_reviews": lambda ctx, session, args: tool_synthesize_reviews(ctx, session),
}


@dataclass
class AgentState:
    """État du graphe pour un tour de conversation. `ctx`/`session` portent
    les ressources partagées et l'état métier (Phase 8, `orchestrator.context`
    / `orchestrator.state`) ; ils ne sont jamais sérialisés (pas de
    checkpointer persistant utilisé ici, uniquement une exécution en mémoire
    par tour Chainlit)."""

    ctx: ToolContext
    session: SessionState
    messages: list[dict[str, Any]] = field(default_factory=list)
    iterations: int = 0
    final_text: str = ""
    tool_executions: list[ToolExecution] = field(default_factory=list)
    pending_tool_calls: list[ToolUse] = field(default_factory=list)


def agent_node(state: AgentState) -> dict[str, Any]:
    result = state.session.bedrock_client.converse_with_tools(
        messages=state.messages,
        tools=TOOL_SPECS,
        system=SYSTEM_PROMPT,
    )
    assistant_message = {"role": "assistant", "content": result.content_blocks}
    return {
        "messages": [*state.messages, assistant_message],
        "iterations": state.iterations + 1,
        "pending_tool_calls": result.tool_calls,
        "final_text": result.text,
    }


def tools_node(state: AgentState) -> dict[str, Any]:
    tool_result_blocks: list[dict[str, Any]] = []
    executions: list[ToolExecution] = []

    for call in state.pending_tool_calls:
        func = TOOL_FUNCTIONS.get(call.name)
        if func is None:
            execution = ToolExecution(
                llm_summary={"ok": False, "error": f"Outil inconnu : {call.name}"}
            )
        else:
            try:
                execution = func(state.ctx, state.session, call.input)
            except Exception as exc:  # noqa: BLE001 - un outil en échec ne doit pas planter la boucle
                logger.exception("L'outil %s a échoué", call.name)
                execution = ToolExecution(llm_summary={"ok": False, "error": str(exc)})

        executions.append(execution)
        status = "success" if execution.llm_summary.get("ok", True) else "error"
        tool_result_blocks.append(
            {
                "toolResult": {
                    "toolUseId": call.tool_use_id,
                    "content": [{"json": execution.llm_summary}],
                    "status": status,
                }
            }
        )

    tool_message = {"role": "user", "content": tool_result_blocks}
    return {
        "messages": [*state.messages, tool_message],
        "tool_executions": [*state.tool_executions, *executions],
        "pending_tool_calls": [],
    }


def route_after_agent(state: AgentState) -> str:
    if state.pending_tool_calls and state.iterations < MAX_TOOL_ITERATIONS:
        return "tools"
    return END


def build_graph() -> Any:
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", route_after_agent, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()


COMPILED_GRAPH = build_graph()


def run_agent_turn(
    ctx: ToolContext,
    session: SessionState,
    user_message: str,
    history: list[dict[str, Any]] | None = None,
) -> AgentState:
    """Exécute un tour complet de la boucle agent (potentiellement plusieurs
    aller-retours outils) pour un message utilisateur, en repartant de
    l'historique de conversation `history` (blocs Bedrock Converse) du tour
    précédent le cas échéant."""
    messages = [*(history or []), {"role": "user", "content": [{"text": user_message}]}]
    initial_state = AgentState(ctx=ctx, session=session, messages=messages)
    result = COMPILED_GRAPH.invoke(initial_state)
    return AgentState(**result) if isinstance(result, dict) else result
