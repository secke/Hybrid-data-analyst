"""Connexions Postgres : moteur applicatif (ingestion) et moteur lecture seule
(exécution du SQL généré par l'agent, à partir de la Phase 1)."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from config.settings import get_settings


@lru_cache
def get_app_engine() -> Engine:
    """Rôle agent_app (lecture/écriture) : utilisé par les scripts d'ingestion."""
    settings = get_settings()
    return create_engine(settings.postgres_dsn, pool_pre_ping=True)


@lru_cache
def get_admin_engine() -> Engine:
    """Rôle superuser : réservé au bootstrap (création de rôles/permissions)."""
    settings = get_settings()
    return create_engine(settings.postgres_admin_dsn, pool_pre_ping=True)


@lru_cache
def get_readonly_engine() -> Engine:
    """Rôle agent_readonly : seul rôle autorisé à exécuter le SQL généré par
    l'agent (Phase 1). Statement timeout imposé au niveau session."""
    settings = get_settings()
    return create_engine(
        settings.postgres_readonly_dsn,
        pool_pre_ping=True,
        connect_args={"options": "-c statement_timeout=30000"},
    )
