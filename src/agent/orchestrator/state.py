"""État de session de l'orchestrateur (Phase 8) : une instance par
conversation utilisateur (Chainlit). Garde le dernier DataFrame récupéré
pour permettre l'enchaînement d'outils (ex: "trace un graphique" après
une question SQL, sans redemander les données)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from agent.observability.traced_bedrock import TracedBedrockClient


@dataclass
class SessionState:
    bedrock_client: TracedBedrockClient = field(default_factory=TracedBedrockClient)
    last_dataframe: pd.DataFrame | None = None
    last_sql: str | None = None
    last_source: str | None = None  # "northwind" | "federated"
    last_chart_png: bytes | None = None
    last_chart_question: str | None = None


@dataclass(frozen=True)
class ToolExecution:
    """`llm_summary` est renvoyé au modèle comme résultat d'outil (doit
    rester compact - jamais les données brutes complètes, conforme au
    principe architectural). `display` porte les artefacts complets pour
    l'interface utilisateur, jamais transmis au LLM."""

    llm_summary: dict[str, Any]
    display: dict[str, Any] = field(default_factory=dict)
