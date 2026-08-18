"""Commentaire du graphique généré, ancré sur l'image réelle (Bedrock,
vision multimodale via l'API Converse - même modèle que la génération SQL).

Effectue un vrai appel Bedrock quand `client` est un `BedrockClient` réel -
comme pour les autres générateurs, cet appel n'est jamais déclenché par
l'agent de build : c'est l'utilisateur qui l'exécute lui-même (voir README,
section Phase 3).
"""

from __future__ import annotations

from agent.llm.protocols import BedrockConverser

SYSTEM_PROMPT = """Tu es un analyste de données qui commente des graphiques. \
Décris UNIQUEMENT ce qui est visible dans l'image fournie : tendances, \
valeurs remarquables, comparaisons entre catégories ou séries, anomalies \
apparentes. Ne mentionne jamais un chiffre exact, une donnée ou une \
tendance que tu ne peux pas lire directement sur le graphique - si un \
élément n'est pas clairement lisible, dis-le plutôt que de l'inventer. \
Réponds en 3 à 5 phrases, en français, sans préambule ni formule de \
politesse."""


def build_vision_messages(question: str, png_bytes: bytes) -> list[dict[str, object]]:
    return [
        {
            "role": "user",
            "content": [
                {"image": {"format": "png", "source": {"bytes": png_bytes}}},
                {
                    "text": (
                        f"Question posée à l'origine du graphique : {question}\n\n"
                        "Commente ce graphique."
                    )
                },
            ],
        }
    ]


def comment_on_chart(question: str, png_bytes: bytes, client: BedrockConverser) -> str:
    messages = build_vision_messages(question, png_bytes)
    result = client.converse(
        messages=messages, system=SYSTEM_PROMPT, max_tokens=512, temperature=0.0
    )
    return result.text.strip()
