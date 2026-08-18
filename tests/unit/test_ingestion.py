from __future__ import annotations

import pandas as pd

from agent.ingestion.load_online_retail import flag_anomalies


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "invoice": ["536365", "536365", "C536379", "536380", "536380"],
            "stock_code": ["85123A", "85123A", "22423", "21730", "21730"],
            "description": ["WHITE MUG", "WHITE MUG", "CAKESTAND", "GLASS STAR", "GLASS STAR"],
            "quantity": [6, 6, -1, 4, 4],
            "invoice_date": pd.to_datetime(["2010-12-01"] * 5),
            "price": [2.55, 2.55, 4.95, 0.0, 0.0],
            "customer_id": [17850.0, 17850.0, None, 17850.0, 17850.0],
            "country": ["United Kingdom"] * 5,
            "source_sheet": ["Year 2010-2011"] * 5,
        }
    )


def test_flag_anomalies_preserves_row_count() -> None:
    df = _sample_df()
    flagged = flag_anomalies(df)
    assert len(flagged) == len(df), "aucune ligne ne doit être supprimée"


def test_flag_anomalies_detects_missing_customer_id() -> None:
    flagged = flag_anomalies(_sample_df())
    assert flagged.loc[2, "anomaly_missing_customer_id"] is True or bool(
        flagged.loc[2, "anomaly_missing_customer_id"]
    )
    assert not bool(flagged.loc[0, "anomaly_missing_customer_id"])


def test_flag_anomalies_detects_cancellation() -> None:
    flagged = flag_anomalies(_sample_df())
    assert bool(flagged.loc[2, "anomaly_cancellation"])
    assert not bool(flagged.loc[0, "anomaly_cancellation"])


def test_flag_anomalies_detects_negative_quantity() -> None:
    flagged = flag_anomalies(_sample_df())
    assert bool(flagged.loc[2, "anomaly_negative_quantity"])


def test_flag_anomalies_detects_non_positive_price() -> None:
    flagged = flag_anomalies(_sample_df())
    assert bool(flagged.loc[3, "anomaly_non_positive_price"])
    assert bool(flagged.loc[4, "anomaly_non_positive_price"])


def test_flag_anomalies_detects_duplicate_row() -> None:
    flagged = flag_anomalies(_sample_df())
    # Lignes 0 et 1 sont des doublons exacts ; seule la seconde est marquée.
    assert not bool(flagged.loc[0, "anomaly_duplicate_row"])
    assert bool(flagged.loc[1, "anomaly_duplicate_row"])
    # Lignes 3 et 4 sont également des doublons exacts.
    assert bool(flagged.loc[4, "anomaly_duplicate_row"])


def test_is_anomalous_aggregates_flags() -> None:
    flagged = flag_anomalies(_sample_df())
    assert bool(flagged.loc[0, "is_anomalous"]) is False
    assert bool(flagged.loc[2, "is_anomalous"]) is True
