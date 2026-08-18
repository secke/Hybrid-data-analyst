"""Génère le SQL fédéré (DuckDB) à partir d'une question cross-source, via
Bedrock (Claude, API Converse).

Comme les autres générateurs, cet appel Bedrock n'est jamais déclenché par
l'agent de build : c'est l'utilisateur qui l'exécute lui-même (voir README,
section Phase 5).
"""

from __future__ import annotations

from agent.llm.bedrock_client import BedrockClient
from agent.llm.extraction import extract_fenced_code
from agent.schema.introspect import TableSchema

SYSTEM_PROMPT = """Tu es un expert DuckDB. Tu génères UNE SEULE requête SQL \
en lecture seule (SELECT, ou UNION/INTERSECT/EXCEPT de SELECT) répondant à \
la question posée, en te basant strictement sur le schéma fourni. Ce schéma \
fédère plusieurs sources hétérogènes dans la même connexion DuckDB :
- Les tables Northwind (ERP/CRM), issues de PostgreSQL.
- La vue `online_retail` (export e-commerce réel, Online Retail II), issue \
d'un fichier Parquet. Les montants (`price`) y sont en GBP.
- Northwind n'a pas de devise explicite : traite ses montants comme USD.

Règles impératives :
- Une seule instruction SQL (SELECT, ou UNION/INTERSECT/EXCEPT de SELECT), \
sans point-virgule final.
- Aucune instruction DML/DDL.
- N'utilise que les tables/vues et colonnes listées dans le schéma fourni.
- Pour comparer des pays entre `online_retail` et les tables Northwind \
(`ship_country`, `country`), utilise la fonction `normalize_country(...)` \
disponible - les noms de pays diffèrent entre les deux sources (ex: "UK" \
vs "United Kingdom", "EIRE" vs "Ireland").
- Réponds uniquement avec le SQL, dans un bloc ```sql ... ```, sans aucune \
autre explication.
"""


def build_schema_context(tables: list[TableSchema], extra_context: str = "") -> str:
    """`extra_context` : faits utiles à la génération non déductibles du
    schéma seul, ex. le taux de change GBP->USD du jour (DuckDB ne peut pas
    appeler d'API réseau - le taux doit être injecté en littéral dans le SQL
    généré)."""
    context = "\n\n".join(t.to_document() for t in tables)
    if extra_context:
        context += f"\n\nContexte supplémentaire:\n{extra_context}"
    return context


def build_user_message(
    question: str,
    schema_context: str,
    previous_sql: str | None = None,
    previous_error: str | None = None,
) -> str:
    message = f"Schéma fédéré disponible:\n{schema_context}\n\nQuestion: {question}"
    if previous_sql and previous_error:
        message += (
            "\n\nTa précédente tentative a échoué.\n"
            f"SQL précédent:\n{previous_sql}\n\n"
            f"Erreur:\n{previous_error}\n\n"
            "Corrige le SQL en tenant compte de cette erreur."
        )
    return message


def generate_federated_sql(
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
    return extract_fenced_code(result.text)
