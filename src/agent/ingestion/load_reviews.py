"""Télécharge un échantillon d'Amazon Reviews (Kaggle) et l'écrit en Parquet.

Nécessite des identifiants Kaggle (KAGGLE_USERNAME + KAGGLE_KEY en variables
d'environnement, ou ~/.kaggle/kaggle.json) : https://www.kaggle.com/settings
-> "Create New Token". Le dataset complet est volumineux (plusieurs millions
de lignes) ; on n'en conserve qu'un échantillon stratifié pour ce projet.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd

from config.settings import get_settings

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
RAW_DATA_DIR = BASE_DIR / "data" / "raw" / "amazon_reviews"
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"

SAMPLE_SIZE = 50_000

# Colonnes attendues pour kritanjalijain/amazon-reviews (dérivé d'Amazon
# Review Polarity) : pas d'en-tête, 3 colonnes (polarité 1/2, titre, texte).
CSV_COLUMNS = ["polarity", "title", "text"]


def _check_kaggle_credentials() -> None:
    has_env = bool(os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"))
    has_file = (Path.home() / ".kaggle" / "kaggle.json").exists()
    if not (has_env or has_file):
        raise RuntimeError(
            "Identifiants Kaggle introuvables. Créez un token sur "
            "https://www.kaggle.com/settings puis exportez KAGGLE_USERNAME "
            "et KAGGLE_KEY, ou placez le fichier téléchargé dans "
            "~/.kaggle/kaggle.json (chmod 600)."
        )


def download_dataset() -> Path:
    _check_kaggle_credentials()
    settings = get_settings()
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # import tardif: la lib lit les credentials Kaggle à l'import
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()

    logger.info("Téléchargement du dataset Kaggle %s", settings.kaggle_dataset)
    api.dataset_download_files(settings.kaggle_dataset, path=str(RAW_DATA_DIR), unzip=True)
    logger.info("Dataset extrait dans %s", RAW_DATA_DIR)
    return RAW_DATA_DIR


def find_csv_files(dataset_dir: Path) -> list[Path]:
    csv_files = sorted(dataset_dir.rglob("*.csv"))
    if not csv_files:
        raise RuntimeError(f"Aucun fichier CSV trouvé dans {dataset_dir}")
    logger.info("Fichiers CSV trouvés: %s", [f.name for f in csv_files])
    return csv_files


def sample_reviews(csv_files: list[Path], sample_size: int = SAMPLE_SIZE) -> pd.DataFrame:
    """Échantillonne au maximum `sample_size` lignes, réparties entre les
    fichiers disponibles (typiquement train.csv / test.csv)."""
    per_file = max(1, sample_size // len(csv_files))
    frames = []
    for csv_path in csv_files:
        logger.info("Échantillonnage de %s (jusqu'à %d lignes)...", csv_path.name, per_file)
        chunk_iter = pd.read_csv(
            csv_path,
            header=None,
            names=CSV_COLUMNS,
            nrows=per_file,
            encoding="utf-8",
        )
        chunk_iter["source_file"] = csv_path.name
        frames.append(chunk_iter)

    combined = pd.concat(frames, ignore_index=True)
    combined["label"] = combined["polarity"].map({1: "negative", 2: "positive"})
    logger.info("Échantillon final: %d avis", len(combined))
    return combined


def write_output(df: pd.DataFrame) -> Path:
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PROCESSED_DATA_DIR / "amazon_reviews_sample.parquet"
    df.to_parquet(output_path, index=False)
    logger.info("Échantillon d'avis écrit dans %s", output_path)
    return output_path


def main() -> None:
    logging.basicConfig(level=get_settings().log_level)
    dataset_dir = download_dataset()
    csv_files = find_csv_files(dataset_dir)
    df = sample_reviews(csv_files)
    write_output(df)


if __name__ == "__main__":
    main()
