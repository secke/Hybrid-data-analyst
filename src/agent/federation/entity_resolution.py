"""Résolution d'entités entre sources : normalise les noms de pays pour
permettre les jointures/unions cross-source entre Northwind (Postgres) et
Online Retail II (Parquet).

Construit à partir de l'inspection réelle des valeurs distinctes des deux
sources : Northwind utilise des codes courts ("UK", "USA"), Online Retail II
des noms plus longs ou des codes historiques ("EIRE" pour l'Irlande, "RSA"
pour l'Afrique du Sud). Les valeurs non listées ici sont déjà cohérentes
entre les deux sources et passent inchangées."""

from __future__ import annotations

COUNTRY_ALIASES: dict[str, str] = {
    "UK": "United Kingdom",
    "EIRE": "Ireland",
    "RSA": "South Africa",
}


def normalize_country(name: str | None) -> str | None:
    if name is None:
        return None
    cleaned = name.strip()
    return COUNTRY_ALIASES.get(cleaned, cleaned)
