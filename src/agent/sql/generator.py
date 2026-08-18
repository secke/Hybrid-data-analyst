"""Génère le SQL à partir d'une question et du contexte de schéma récupéré,
via Bedrock (Claude, API Converse).

Ce module effectue un vrai appel Bedrock quand `client` est un
`BedrockClient` réel - conformément au choix du projet, cet appel n'est pas
déclenché par l'agent de build : c'est l'utilisateur qui l'exécute lui-même
(voir README, section Phase 1)."""

from __future__ import annotations

from agent.llm.bedrock_client import BedrockClient
from agent.llm.extraction import extract_fenced_code

SYSTEM_PROMPT = """Tu es un expert PostgreSQL. Tu génères UNE SEULE requête \
SQL en lecture seule (SELECT uniquement) répondant à la question posée, en \
te basant strictement sur le schéma fourni. Règles impératives :
- Une seule instruction SQL, sans point-virgule final.
- Aucune instruction DML/DDL (INSERT, UPDATE, DELETE, CREATE, DROP, ALTER).
- N'utilise que les tables et colonnes listées dans le schéma fourni.
- Réponds uniquement avec le SQL, dans un bloc ```sql ... ```, sans aucune \
autre explication.
"""

def _extract_sql(text: str) -> str:
    return extract_fenced_code(text)


def build_user_message(
    question: str,
    schema_context: str,
    previous_sql: str | None = None,
    previous_error: str | None = None,
) -> str:
    message = f"Schéma disponible:\n{schema_context}\n\nQuestion: {question}"
    if previous_sql and previous_error:
        message += (
            "\n\nTa précédente tentative a échoué.\n"
            f"SQL précédent:\n{previous_sql}\n\n"
            f"Erreur:\n{previous_error}\n\n"
            "Corrige le SQL en tenant compte de cette erreur."
        )
    return message


def generate_sql(
    question: str,
    schema_context: str,
    client: BedrockClient,
    previous_sql: str | None = None,
    previous_error: str | None = None,
) -> str:
    user_content = build_user_message(question, schema_context, previous_sql, previous_error)
    messages = [{"role": "user", "content": [{"text": user_content}]}]
    result = client.converse(
        messages=messages, system=SYSTEM_PROMPT, max_tokens=1024, temperature=0.0
    )
    return _extract_sql(result.text)
