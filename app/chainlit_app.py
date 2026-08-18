"""Interface de chat Chainlit (Phase 8), branchée sur l'agent LangGraph
(`agent.orchestrator.graph`) : l'agent décide seul quels outils appeler
(Phases 1-6) pour répondre à la question de l'utilisateur - il n'y a pas de
routage explicite ici, seulement l'affichage des artefacts qu'il produit.

Le contexte d'outils et l'état de session (Phase 8) sont construits une fois
par connexion Chainlit (`on_chat_start`) et réutilisés pour chaque message,
ce qui permet d'enchaîner les questions (ex: "trace un graphique" après une
question SQL) sans perdre le contexte de la conversation.

Démarrage : `uv run chainlit run app/chainlit_app.py`. Chaque appel Bedrock
est déclenché par l'utilisateur qui interagit avec l'interface, jamais par
l'agent de build."""

from __future__ import annotations

import logging
from typing import Any

import chainlit as cl

from agent.audit.journal import current_identity
from agent.feedback.store import FeedbackEntry, save_feedback
from agent.orchestrator.context import ToolContext
from agent.orchestrator.graph import run_agent_turn
from agent.orchestrator.state import SessionState, ToolExecution

logger = logging.getLogger(__name__)

WELCOME_MESSAGE = (
    "Prêt. Posez une question sur Northwind ou Online Retail II, ou "
    "demandez un calcul, un graphique, un export ou un rapport sur les "
    "dernières données récupérées."
)


@cl.on_chat_start
async def on_chat_start() -> None:
    building = cl.Message(content="Construction du contexte (schéma, index)...")
    await building.send()

    ctx = await cl.make_async(ToolContext.build)()
    cl.user_session.set("ctx", ctx)
    cl.user_session.set("session", SessionState())
    cl.user_session.set("history", [])

    await cl.Message(content=WELCOME_MESSAGE).send()


def _render_tool_execution(execution: ToolExecution) -> cl.Message | None:
    """Traduit le `display` d'un `ToolExecution` (Phase 8) en éléments
    Chainlit. Un seul de ces blocs `if` correspond, chaque outil produisant
    une combinaison de clés qui lui est propre (voir `agent.orchestrator.tools`)."""
    if not execution.llm_summary.get("ok", True):
        error = execution.llm_summary.get("error", "Échec de l'outil.")
        return cl.Message(content=f"⚠️ {error}")

    display = execution.display

    if "dataframe" in display:
        elements: list[Any] = []
        if display.get("sql"):
            elements.append(cl.Text(name="Requête SQL", content=display["sql"], language="sql"))
        elements.append(cl.Dataframe(name="Résultat", data=display["dataframe"]))
        row_count = execution.llm_summary.get("row_count", len(display["dataframe"]))
        return cl.Message(content=f"{row_count} ligne(s) trouvée(s).", elements=elements)

    if "chart_png" in display:
        elements = [cl.Image(name="Graphique", content=display["chart_png"], display="inline")]
        return cl.Message(content=display.get("commentary", ""), elements=elements)

    if "code" in display:
        elements = [cl.Text(name="Code Python", content=display["code"], language="python")]
        if display.get("result_dataframe") is not None:
            elements.append(cl.Dataframe(name="Résultat", data=display["result_dataframe"]))
            content = "Calcul effectué."
        else:
            content = f"Résultat : {execution.llm_summary.get('result')}"
        return cl.Message(content=content, elements=elements)

    if "files" in display:
        elements = [cl.File(name=f"export.{fmt}", url=url) for fmt, url in display["files"].items()]
        return cl.Message(content="Fichiers exportés :", elements=elements)

    if "url" in display and "narrative" in display:
        elements = [cl.Pdf(name="rapport.pdf", url=display["url"])]
        return cl.Message(content=display["narrative"], elements=elements)

    if "synthesis" in display:
        return cl.Message(content=display["synthesis"])

    return None


@cl.on_message
async def on_message(message: cl.Message) -> None:
    ctx: ToolContext = cl.user_session.get("ctx")
    session: SessionState = cl.user_session.get("session")
    history: list[dict[str, Any]] = cl.user_session.get("history") or []

    async with cl.Step(name="Agent", type="run") as step:
        final_state = await cl.make_async(run_agent_turn)(ctx, session, message.content, history)
        step.output = final_state.final_text

    cl.user_session.set("history", final_state.messages)

    for execution in final_state.tool_executions:
        rendered = _render_tool_execution(execution)
        if rendered is not None:
            await rendered.send()

    answer = final_state.final_text or (
        "Je n'ai pas pu formuler de réponse complète - essayez de reformuler la question."
    )
    actions = [
        cl.Action(
            name="feedback_helpful",
            payload={"question": message.content, "sql": session.last_sql or ""},
            label="👍 Utile",
        ),
        cl.Action(
            name="feedback_not_helpful",
            payload={"question": message.content, "sql": session.last_sql or ""},
            label="👎 Pas utile",
        ),
    ]
    await cl.Message(content=answer, actions=actions).send()


async def _record_feedback(action: cl.Action, rating: str) -> None:
    entry = FeedbackEntry(
        question=action.payload.get("question", ""),
        sql_executed=action.payload.get("sql") or None,
        rating=rating,
        identity=current_identity(),
    )
    await cl.make_async(save_feedback)(entry)
    await action.remove()
    await cl.Message(content="Merci pour votre retour.").send()


@cl.action_callback("feedback_helpful")
async def on_feedback_helpful(action: cl.Action) -> None:
    await _record_feedback(action, "helpful")


@cl.action_callback("feedback_not_helpful")
async def on_feedback_not_helpful(action: cl.Action) -> None:
    await _record_feedback(action, "not_helpful")
