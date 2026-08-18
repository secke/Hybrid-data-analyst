"""Connexion DuckDB fédérée (Phase 5) : attache Northwind (Postgres, via le
rôle en lecture seule `agent_readonly`) et enregistre les sources Parquet
(Online Retail II, avis Amazon si l'ingestion Kaggle a été faite) comme vues
locales aplaties - une vue par table/source, même nom, pas de préfixe de
catalogue, pour rester cohérent avec l'approche Phase 1 (schéma plat,
validateur SQL réutilisable tel quel).

Toute la fédération reste en lecture seule : l'attache Postgres est
`READ_ONLY`, les vues Parquet ne permettent pas d'écriture sur les fichiers
sources.
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

from agent.federation.entity_resolution import normalize_country
from config.settings import get_settings

logger = logging.getLogger(__name__)

PROCESSED_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "processed"
POSTGRES_CATALOG_ALIAS = "northwind_pg"

PARQUET_SOURCES = {
    "online_retail": PROCESSED_DATA_DIR / "online_retail.parquet",
    "amazon_reviews": PROCESSED_DATA_DIR / "amazon_reviews_sample.parquet",
}


def _attach_postgres(con: duckdb.DuckDBPyConnection) -> list[str]:
    settings = get_settings()
    con.execute("INSTALL postgres")
    con.execute("LOAD postgres")

    attach_str = (
        f"host={settings.postgres_host} port={settings.postgres_port} "
        f"dbname={settings.postgres_db} user={settings.postgres_readonly_user} "
        f"password={settings.postgres_readonly_password}"
    )
    con.execute(f"ATTACH '{attach_str}' AS {POSTGRES_CATALOG_ALIAS} (TYPE postgres, READ_ONLY)")

    tables = con.execute(
        "SELECT table_name FROM duckdb_tables() "
        "WHERE database_name = ? AND schema_name = 'public'",
        [POSTGRES_CATALOG_ALIAS],
    ).fetchall()

    created = []
    for (table_name,) in tables:
        con.execute(
            f'CREATE VIEW "{table_name}" AS '
            f'SELECT * FROM {POSTGRES_CATALOG_ALIAS}.public."{table_name}"'
        )
        created.append(table_name)
    return created


def _register_parquet_sources(con: duckdb.DuckDBPyConnection) -> list[str]:
    con.execute("INSTALL parquet")
    con.execute("LOAD parquet")

    created = []
    for view_name, path in PARQUET_SOURCES.items():
        if not path.exists():
            logger.warning(
                "Source Parquet '%s' introuvable (%s) - vue non créée", view_name, path
            )
            continue
        con.execute(f"CREATE VIEW {view_name} AS SELECT * FROM read_parquet('{path}')")
        created.append(view_name)
    return created


def get_federated_connection() -> duckdb.DuckDBPyConnection:
    """Ouvre une nouvelle connexion DuckDB fédérée. Chaque appel crée une
    connexion indépendante (DuckDB en mémoire, pas de partage d'état)."""
    con = duckdb.connect()
    postgres_views = _attach_postgres(con)
    parquet_views = _register_parquet_sources(con)
    con.create_function("normalize_country", normalize_country, ["VARCHAR"], "VARCHAR")

    logger.info(
        "Connexion fédérée prête: %d tables Postgres, %d sources Parquet",
        len(postgres_views),
        len(parquet_views),
    )
    return con
