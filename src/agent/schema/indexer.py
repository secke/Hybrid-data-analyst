"""Indexe les documents de schéma (une table = un document) dans Qdrant.

`index_schema` prend un embedder en paramètre (protocole `Embedder`) plutôt
que d'instancier `TitanEmbeddingsClient` en dur : cela permet de tester tout
le chemin Qdrant (création de collection, upsert, recherche) avec un embedder
factice, sans appel Bedrock réel. `main()` est le point d'entrée qui utilise
le vrai `TitanEmbeddingsClient` - à exécuter manuellement par l'utilisateur.
"""

from __future__ import annotations

import logging

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from agent.llm.protocols import Embedder
from agent.schema.introspect import TableSchema
from config.settings import get_settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 1024


def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url)


def ensure_collection(client: QdrantClient, collection_name: str | None = None) -> str:
    settings = get_settings()
    name = collection_name or settings.qdrant_collection
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
        logger.info("Collection Qdrant '%s' créée", name)
    return name


def index_schema(
    tables: list[TableSchema],
    embedder: Embedder,
    client: QdrantClient | None = None,
    collection_name: str | None = None,
) -> int:
    client = client or get_qdrant_client()
    name = ensure_collection(client, collection_name)

    points = []
    for i, table in enumerate(tables):
        document = table.to_document()
        result = embedder.embed(document)
        points.append(
            PointStruct(
                id=i,
                vector=result.vector,
                payload={"table_name": table.name, "document": document},
            )
        )

    client.upsert(collection_name=name, points=points)
    logger.info("%d tables indexées dans la collection '%s'", len(points), name)
    return len(points)


def main() -> None:
    """Point d'entrée réel : appelle Bedrock (Titan Embeddings). À lancer
    manuellement (`python -m agent.schema.indexer`) - non exécuté par l'agent
    de build lui-même."""
    from agent.db.postgres import get_readonly_engine
    from agent.llm.embeddings import TitanEmbeddingsClient
    from agent.schema.introspect import introspect_schema

    logging.basicConfig(level=get_settings().log_level)
    tables = introspect_schema(get_readonly_engine())
    embedder = TitanEmbeddingsClient()
    index_schema(tables, embedder)


if __name__ == "__main__":
    main()
