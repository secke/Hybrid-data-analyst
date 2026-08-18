"""Télécharge et nettoie Online Retail II (UCI).

Principe : les anomalies connues du jeu de données (identifiants clients
manquants, annulations, doublons, quantités/prix négatifs) sont détectées et
*loguées*, mais aucune ligne n'est supprimée silencieusement. Le Parquet
produit contient toutes les lignes d'origine avec des colonnes de drapeaux
booléens ; un second Parquet ne contient que les lignes anormales, pour audit.
"""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path

import pandas as pd
import requests

from config.settings import get_settings

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
RAW_DATA_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
ANOMALIES_DIR = BASE_DIR / "data" / "logs" / "anomalies"

COLUMN_RENAME = {
    "Invoice": "invoice",
    "StockCode": "stock_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "invoice_date",
    "Price": "price",
    "Customer ID": "customer_id",
    "Country": "country",
}


def download_and_extract() -> Path:
    settings = get_settings()
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    xlsx_path = RAW_DATA_DIR / "online_retail_II.xlsx"

    if xlsx_path.exists():
        logger.info("%s déjà présent, téléchargement ignoré", xlsx_path)
        return xlsx_path

    logger.info("Téléchargement de Online Retail II depuis %s", settings.online_retail_xlsx_url)
    response = requests.get(settings.online_retail_xlsx_url, timeout=120)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".xlsx")]
        if not names:
            raise RuntimeError("Aucun fichier .xlsx trouvé dans l'archive Online Retail II")
        with zf.open(names[0]) as src, xlsx_path.open("wb") as dst:
            dst.write(src.read())

    logger.info("Fichier extrait vers %s", xlsx_path)
    return xlsx_path


def load_raw(xlsx_path: Path) -> pd.DataFrame:
    logger.info("Lecture des feuilles Excel (peut prendre une minute)...")
    sheets = pd.read_excel(xlsx_path, sheet_name=None, engine="openpyxl")
    frames = []
    for sheet_name, df in sheets.items():
        df = df.rename(columns=COLUMN_RENAME)
        df["source_sheet"] = sheet_name
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)
    # Excel stocke invoice/stock_code/description tantôt en numérique tantôt
    # en texte (ex: "C489449" pour une annulation) -> dtype object mixte,
    # à uniformiser en string tout en préservant les valeurs manquantes.
    for col in ("invoice", "stock_code", "description"):
        combined[col] = combined[col].apply(lambda v: v if pd.isna(v) else str(v)).astype("string")
    logger.info("Total: %d lignes chargées depuis %d feuilles", len(combined), len(sheets))
    return combined


def flag_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute des colonnes booléennes de drapeau, sans jamais retirer de ligne."""
    df = df.copy()

    df["anomaly_missing_customer_id"] = df["customer_id"].isna()
    df["anomaly_cancellation"] = df["invoice"].astype(str).str.startswith("C")
    df["anomaly_negative_quantity"] = df["quantity"] < 0
    df["anomaly_non_positive_price"] = df["price"] <= 0
    df["anomaly_duplicate_row"] = df.drop(columns=["source_sheet"]).duplicated(keep="first")

    anomaly_cols = [c for c in df.columns if c.startswith("anomaly_")]
    df["is_anomalous"] = df[anomaly_cols].any(axis=1)

    return df


def log_anomaly_summary(df: pd.DataFrame) -> None:
    anomaly_cols = [c for c in df.columns if c.startswith("anomaly_")]
    for col in anomaly_cols:
        count = int(df[col].sum())
        logger.info("Anomalie [%s]: %d lignes (%.2f%%)", col, count, 100 * count / len(df))
    logger.info(
        "Total lignes anormales: %d / %d (%.2f%%)",
        int(df["is_anomalous"].sum()),
        len(df),
        100 * df["is_anomalous"].sum() / len(df),
    )


def write_outputs(df: pd.DataFrame) -> tuple[Path, Path]:
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    ANOMALIES_DIR.mkdir(parents=True, exist_ok=True)

    processed_path = PROCESSED_DATA_DIR / "online_retail.parquet"
    df.to_parquet(processed_path, index=False)
    logger.info("Jeu de données complet (anomalies conservées) écrit dans %s", processed_path)

    anomalies_path = ANOMALIES_DIR / "online_retail_anomalies.parquet"
    df[df["is_anomalous"]].to_parquet(anomalies_path, index=False)
    logger.info("Sous-ensemble des anomalies écrit dans %s (audit)", anomalies_path)

    return processed_path, anomalies_path


def main() -> None:
    logging.basicConfig(level=get_settings().log_level)
    xlsx_path = download_and_extract()
    df = load_raw(xlsx_path)
    df = flag_anomalies(df)
    log_anomaly_summary(df)
    write_outputs(df)


if __name__ == "__main__":
    main()
