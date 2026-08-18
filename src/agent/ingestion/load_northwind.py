"""Télécharge le dump SQL Northwind et le charge dans Postgres (base `northwind`,
propriétaire `agent_app`), puis accorde le SELECT à `agent_readonly`.

Le dump contient des instructions multi-statements (DROP/CREATE/INSERT) qu'il
est plus fiable d'exécuter via le client `psql` (protocole simple query) que
de les reparser nous-mêmes. On utilise `psql` en local s'il est installé,
sinon on l'exécute dans le conteneur Postgres du docker-compose.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

import requests
from sqlalchemy import text

from agent.db.postgres import get_app_engine
from config.settings import get_settings

logger = logging.getLogger(__name__)

RAW_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"


def download_dump() -> Path:
    settings = get_settings()
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DATA_DIR / "northwind.sql"

    logger.info("Téléchargement du dump Northwind depuis %s", settings.northwind_sql_url)
    response = requests.get(settings.northwind_sql_url, timeout=30)
    response.raise_for_status()
    dest.write_bytes(response.content)
    logger.info("Dump écrit dans %s (%d octets)", dest, len(response.content))
    return dest


def _run_psql_local(dump_path: Path) -> None:
    settings = get_settings()
    cmd = [
        "psql",
        f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}",
        "-v",
        "ON_ERROR_STOP=1",
        "-f",
        str(dump_path),
    ]
    subprocess.run(cmd, check=True)  # noqa: S603


def _run_psql_in_container(dump_path: Path) -> None:
    settings = get_settings()
    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "-e",
        f"PGPASSWORD={settings.postgres_password}",
        "postgres",
        "psql",
        "-U",
        settings.postgres_user,
        "-d",
        settings.postgres_db,
        "-v",
        "ON_ERROR_STOP=1",
    ]
    with dump_path.open("rb") as f:
        subprocess.run(cmd, stdin=f, check=True)  # noqa: S603


def load_dump(dump_path: Path) -> None:
    logger.info("Chargement du dump Northwind dans Postgres...")
    if shutil.which("psql"):
        _run_psql_local(dump_path)
    else:
        logger.info("psql non trouvé en local, exécution via le conteneur docker-compose")
        _run_psql_in_container(dump_path)
    logger.info("Dump Northwind chargé avec succès")


def grant_readonly_access() -> None:
    settings = get_settings()
    ro_user = settings.postgres_readonly_user
    engine = get_app_engine()
    with engine.begin() as conn:
        conn.execute(text(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {ro_user}"))
        conn.execute(
            text(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {ro_user}")
        )
    logger.info("Droits SELECT accordés à %s sur le schéma Northwind", ro_user)


def main() -> None:
    logging.basicConfig(level=get_settings().log_level)
    dump_path = download_dump()
    load_dump(dump_path)
    grant_readonly_access()


if __name__ == "__main__":
    main()
