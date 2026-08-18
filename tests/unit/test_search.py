from __future__ import annotations

from unittest.mock import MagicMock

from agent.schema.introspect import ColumnInfo, TableSchema
from agent.schema.search import BM25SchemaIndex, reciprocal_rank_fusion, vector_search


def _tables() -> list[TableSchema]:
    return [
        TableSchema(
            name="orders",
            columns=[
                ColumnInfo("order_id", "smallint", False),
                ColumnInfo("customer_id", "character varying", True),
                ColumnInfo("freight", "real", True),
            ],
        ),
        TableSchema(
            name="products",
            columns=[
                ColumnInfo("product_id", "smallint", False),
                ColumnInfo("product_name", "character varying", False),
                ColumnInfo("unit_price", "real", True),
            ],
        ),
        TableSchema(
            name="customers",
            columns=[
                ColumnInfo("customer_id", "character varying", False),
                ColumnInfo("company_name", "character varying", False),
            ],
        ),
    ]


def test_bm25_ranks_matching_table_first() -> None:
    index = BM25SchemaIndex(_tables())
    results = index.search("orders order_id freight", top_k=3)
    assert results[0][0] == "orders"


def test_bm25_returns_top_k_results() -> None:
    index = BM25SchemaIndex(_tables())
    results = index.search("product_name unit_price", top_k=1)
    assert len(results) == 1
    assert results[0][0] == "products"


def test_reciprocal_rank_fusion_favors_items_ranked_high_in_both_lists() -> None:
    bm25_ranked = [("orders", 5.0), ("products", 1.0), ("customers", 0.5)]
    vector_ranked = [("orders", 0.9), ("customers", 0.5), ("products", 0.2)]

    fused = reciprocal_rank_fusion([bm25_ranked, vector_ranked])

    assert fused[0][0] == "orders"  # premier dans les deux classements


def test_reciprocal_rank_fusion_includes_items_from_a_single_list() -> None:
    bm25_ranked = [("orders", 5.0)]
    vector_ranked: list[tuple[str, float]] = []

    fused = reciprocal_rank_fusion([bm25_ranked, vector_ranked])

    assert dict(fused)["orders"] > 0


def test_vector_search_calls_embedder_and_qdrant() -> None:
    fake_embedder = MagicMock()
    fake_embedder.embed.return_value = MagicMock(vector=[0.1, 0.2, 0.3])

    fake_hit = MagicMock()
    fake_hit.payload = {"table_name": "orders"}
    fake_hit.score = 0.87

    fake_client = MagicMock()
    fake_client.query_points.return_value = MagicMock(points=[fake_hit])

    results = vector_search("ma question", fake_embedder, fake_client, "schema_index", top_k=5)

    fake_embedder.embed.assert_called_once_with("ma question")
    fake_client.query_points.assert_called_once()
    assert results == [("orders", 0.87)]


def test_vector_search_skips_hits_without_payload() -> None:
    fake_embedder = MagicMock()
    fake_embedder.embed.return_value = MagicMock(vector=[0.1])

    fake_hit = MagicMock()
    fake_hit.payload = None

    fake_client = MagicMock()
    fake_client.query_points.return_value = MagicMock(points=[fake_hit])

    results = vector_search("q", fake_embedder, fake_client, "schema_index")
    assert results == []
