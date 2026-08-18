"""Génère le code Python (pandas) d'analyse à partir d'une question et d'un
DataFrame d'entrée, via Bedrock (Claude, API Converse).

Comme pour `agent.sql.generator`, cet appel Bedrock n'est déclenché par
l'agent de build à aucun moment : c'est l'utilisateur qui l'exécute lui-même
(voir README, section Phase 2).
"""

from __future__ import annotations

import pandas as pd

from agent.llm.extraction import extract_fenced_code
from agent.llm.protocols import BedrockConverser

SYSTEM_PROMPT = """Tu es un expert en analyse de données avec pandas. Tu \
écris UNIQUEMENT du code Python répondant à la question posée, à partir du \
DataFrame `df` déjà chargé (voir aperçu fourni). Règles impératives :
- Le DataFrame d'entrée s'appelle `df` et est déjà disponible - ne le \
recharge jamais et ne le recrée jamais depuis une autre source.
- `pandas` est disponible sous le nom `pd`, `numpy` sous le nom `np`.
- Affecte le résultat final à une variable nommée `result` (DataFrame, \
nombre, chaîne, liste ou dict - jamais un objet non sérialisable).
- Aucun accès réseau, fichier ou sous-processus : uniquement du calcul sur \
`df` avec pandas/numpy.
- Réponds uniquement avec le code, dans un bloc ```python ... ```, sans \
aucune autre explication.
"""


def describe_dataframe(df: pd.DataFrame, sample_rows: int = 5) -> str:
    """Aperçu textuel du DataFrame injecté dans le prompt : colonnes, types
    et un échantillon de lignes - jamais les données complètes (conforme au
    principe architectural : le LLM ne reçoit que ce qui est explicitement
    injecté dans le prompt)."""
    lines = [f"DataFrame `df` : {len(df)} lignes. Colonnes :"]
    for col, dtype in df.dtypes.items():
        lines.append(f"  - {col} ({dtype})")
    n = min(sample_rows, len(df))
    lines.append(f"Aperçu ({n} première(s) ligne(s)) :")
    lines.append(df.head(n).to_string())
    return "\n".join(lines)


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


def generate_code(
    question: str,
    df: pd.DataFrame,
    client: BedrockConverser,
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
