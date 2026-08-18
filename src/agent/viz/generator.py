"""Génère le code Python (Plotly) d'un graphique à partir d'une question et
d'un DataFrame d'entrée, via Bedrock (Claude, API Converse).

Comme pour `agent.python_exec.generator`, cet appel Bedrock n'est jamais
déclenché par l'agent de build : c'est l'utilisateur qui l'exécute lui-même
(voir README, section Phase 3).
"""

from __future__ import annotations

import pandas as pd

from agent.llm.bedrock_client import BedrockClient
from agent.llm.extraction import extract_fenced_code
from agent.python_exec.generator import describe_dataframe

SYSTEM_PROMPT = """Tu es un expert en visualisation de données avec Plotly. \
Tu écris UNIQUEMENT du code Python créant UN SEUL graphique répondant à la \
question posée, à partir du DataFrame `df` déjà chargé (voir aperçu fourni). \
Règles impératives :
- Le DataFrame d'entrée s'appelle `df` et est déjà disponible - ne le \
recharge jamais et ne le recrée jamais depuis une autre source.
- Utilise `plotly.graph_objects` ou `plotly.express` (déjà installés).
- Affecte la figure finale à une variable nommée `fig` \
(plotly.graph_objects.Figure).
- Choisis un type de graphique adapté à la question (barres, ligne, nuage \
de points, histogramme...) et donne-lui un titre clair ainsi que des \
libellés d'axes explicites.
- Aucun accès réseau, fichier ou sous-processus : uniquement du calcul sur \
`df` avec pandas/numpy/plotly.
- Réponds uniquement avec le code, dans un bloc ```python ... ```, sans \
aucune autre explication.
"""


def build_user_message(
    question: str,
    dataframe_description: str,
    previous_code: str | None = None,
    previous_error: str | None = None,
) -> str:
    message = f"{dataframe_description}\n\nQuestion: {question}"
    if previous_code and previous_error:
        message += (
            "\n\nTa précédente tentative a échoué à l'exécution.\n"
            f"Code précédent:\n{previous_code}\n\n"
            f"Erreur:\n{previous_error}\n\n"
            "Corrige le code en tenant compte de cette erreur."
        )
    return message


def generate_chart_code(
    question: str,
    df: pd.DataFrame,
    client: BedrockClient,
    previous_code: str | None = None,
    previous_error: str | None = None,
) -> str:
    description = describe_dataframe(df)
    user_content = build_user_message(question, description, previous_code, previous_error)
    messages = [{"role": "user", "content": [{"text": user_content}]}]
    result = client.converse(
        messages=messages, system=SYSTEM_PROMPT, max_tokens=1536, temperature=0.0
    )
    return extract_fenced_code(result.text)
