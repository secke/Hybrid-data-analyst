"""Recherche hybride (BM25 local + vecteurs Qdrant) avec fusion par
Reciprocal Rank Fusion (RRF). La fusion est purement algorithmique (aucun
appel LLM supplémentaire au-delà de l'embedding de la question, déjà
nécessaire une fois par requête pour la partie vectorielle)."""

from __future__ import annotations

import re

from qdrant_client import QdrantClient
from rank_bm25 import BM25Okapi

from agent.llm.protocols import Embedder
from agent.schema.introspect import TableSchema

RRF_K = 60


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


class BM25SchemaIndex:
    """Index BM25 local sur les documents de schéma - aucun appel réseau."""

    def __init__(self, tables: list[TableSchema]) -> None:
        self._table_names = [t.name for t in tables]
        corpus = [_tokenize(t.to_document()) for t in tables]
        self._bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(
            zip(self._table_names, scores, strict=True),
            key=lambda pair: pair[1],
            reverse=True,
        )
        return ranked[:top_k]


def vector_search(
    query: str,
    embedder: Embedder,
    client: QdrantClient,
    collection_name: str,
    top_k: int = 5,
) -> list[tuple[str, float]]:
    result = embedder.embed(query)
    hits = client.query_points(
        collection_name=collection_name, query=result.vector, limit=top_k
    ).points
    return [(hit.payload["table_name"], hit.score) for hit in hits if hit.payload]


def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[str, float]]], k: int = RRF_K
) -> list[tuple[str, float]]:
    """score(d) = somme, sur chaque classement où d apparaît, de 1/(k + rang)."""
    fused: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, (name, _score) in enumerate(ranked, start=1):
            fused[name] = fused.get(name, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda pair: pair[1], reverse=True)


def hybrid_search(
    query: str,
    bm25_index: BM25SchemaIndex,
    embedder: Embedder,
    client: QdrantClient,
    collection_name: str,
    top_k: int = 5,
) -> list[str]:
    bm25_ranked = bm25_index.search(query, top_k=top_k * 2)
    vector_ranked = vector_search(query, embedder, client, collection_name, top_k=top_k * 2)
    fused = reciprocal_rank_fusion([bm25_ranked, vector_ranked])
    return [name for name, _score in fused[:top_k]]
