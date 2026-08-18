"""Génère un rapport narratif à partir d'un résultat SQL déjà exécuté, en
exigeant que chaque affirmation chiffrée soit reliée à une ligne précise du
tableau de données fourni (traçabilité systématique, Phase 6).

Comme les autres générateurs, cet appel Bedrock n'est jamais déclenché par
l'agent de build : c'est l'utilisateur qui l'exécute lui-même (voir README,
section Phase 6).
"""

from __future__ import annotations

import pandas as pd

from agent.llm.protocols import BedrockConverser
from agent.python_exec.generator import describe_dataframe

SYSTEM_PROMPT = """Tu es un analyste qui rédige un rapport narratif à partir \
de données déjà calculées (jamais de calcul de ton cru). Règles impératives :
- Chaque affirmation contenant un chiffre doit se terminer par une référence \
entre crochets à l'index de ligne du tableau qui la justifie (l'index est \
affiché à gauche de chaque ligne), ex: "Le Royaume-Uni génère le plus de \
lignes (981 330) [Réf: index 0]."
- N'affirme jamais un chiffre qui n'apparaît pas explicitement dans le \
tableau fourni. Si une déduction simple est nécessaire (somme, pourcentage \
entre deux lignes), précise le calcul entre parenthèses et référence les \
index utilisés.
- Structure : un titre (# ...), 3 à 6 paragraphes courts, une phrase de \
synthèse finale.
- Réponds en français, sans préambule ni bloc de code - texte brut avec des \
titres markdown (#, ##)."""


def build_user_message(question: str, data_description: str, sql: str | None) -> str:
    message = f"Question: {question}\n\n{data_description}"
    if sql:
        message += f"\n\nSQL exécuté:\n{sql}"
    message += "\n\nRédige le rapport narratif."
    return message


def generate_narrative(
    question: str,
    df: pd.DataFrame,
    client: BedrockConverser,
    sql: str | None = None,
) -> str:
    data_description = describe_dataframe(df, sample_rows=len(df))
    user_content = build_user_message(question, data_description, sql)
    messages = [{"role": "user", "content": [{"text": user_content}]}]
    result = client.converse(
        messages=messages, system=SYSTEM_PROMPT, max_tokens=2048, temperature=0.0
    )
    return result.text.strip()
