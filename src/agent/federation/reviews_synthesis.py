"""Synthèse qualitative des avis clients (Bedrock, Claude) intégrée au
rapport chiffré (Phase 5). Échantillonne les avis Amazon disponibles
(Parquet, produit par `agent.ingestion.load_reviews` - nécessite des
identifiants Kaggle) et demande une synthèse structurée.

Comme les autres générateurs, cet appel Bedrock n'est jamais déclenché par
l'agent de build : c'est l'utilisateur qui l'exécute lui-même (voir README,
section Phase 5).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from agent.llm.bedrock_client import BedrockClient

REVIEWS_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "processed" / "amazon_reviews_sample.parquet"
)

SYSTEM_PROMPT = """Tu es un analyste qui synthétise des avis clients. À \
partir de l'échantillon d'avis fourni, produis une synthèse structurée en \
français :
- 2-3 points positifs récurrents
- 2-3 points négatifs récurrents
- Un ton général (positif/négatif/mitigé)
Ne généralise jamais au-delà de ce que l'échantillon fourni permet de dire \
- précise que c'est basé sur un échantillon, pas l'ensemble des avis. \
Réponds en 5 à 8 phrases, sans préambule."""


def reviews_available(path: Path = REVIEWS_PATH) -> bool:
    return path.exists()


def sample_reviews(n: int = 50, random_state: int = 42, path: Path = REVIEWS_PATH) -> pd.DataFrame:
    """Lève FileNotFoundError si l'échantillon d'avis n'a pas été ingéré -
    jamais d'échec silencieux ni de synthèse inventée sans données réelles."""
    if not path.exists():
        raise FileNotFoundError(
            f"Aucun échantillon d'avis trouvé ({path}). "
            "Lancez d'abord: uv run python -m agent.ingestion.load_reviews "
            "(nécessite des identifiants Kaggle)."
        )
    df = pd.read_parquet(path)
    return df.sample(n=min(n, len(df)), random_state=random_state)


def format_reviews_for_prompt(df: pd.DataFrame, max_chars_per_review: int = 300) -> str:
    lines = []
    for i, row in enumerate(df.itertuples(index=False), start=1):
        label = getattr(row, "label", "?")
        text = str(getattr(row, "text", ""))[:max_chars_per_review]
        lines.append(f"{i}. [{label}] {text}")
    return "\n".join(lines)


def synthesize_reviews(df: pd.DataFrame, client: BedrockClient) -> str:
    reviews_text = format_reviews_for_prompt(df)
    user_content = (
        f"Échantillon de {len(df)} avis clients:\n\n{reviews_text}\n\nProduis la synthèse."
    )
    messages = [{"role": "user", "content": [{"text": user_content}]}]
    result = client.converse(
        messages=messages, system=SYSTEM_PROMPT, max_tokens=512, temperature=0.0
    )
    return result.text.strip()
