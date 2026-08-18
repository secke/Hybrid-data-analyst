"""Configuration centralisée, lue depuis les variables d'environnement (.env en dev).

Aucune credential n'est jamais codée en dur ici : soit un profil AWS local,
soit des variables d'environnement injectées par un gestionnaire de secrets.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # AWS / Bedrock
    aws_region: str = "us-west-2"
    aws_profile: str | None = None
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    bedrock_max_retries: int = 5
    bedrock_timeout_seconds: int = 60

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "northwind"
    postgres_user: str = "agent_app"
    postgres_password: str = "change_me"
    postgres_admin_user: str = "postgres"
    postgres_admin_password: str = "change_me_admin"
    postgres_readonly_user: str = "agent_readonly"
    postgres_readonly_password: str = "change_me_readonly"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "schema_index"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "change_me_minio"
    minio_bucket_artifacts: str = "artifacts"
    minio_secure: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Langfuse
    langfuse_host: str = "http://localhost:3001"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    # Sources de données
    frankfurter_api_url: str = "https://api.frankfurter.dev/v1"
    northwind_sql_url: str = "https://raw.githubusercontent.com/pthom/northwind_psql/master/northwind.sql"
    online_retail_xlsx_url: str = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
    kaggle_dataset: str = "kritanjalijain/amazon-reviews"

    # Sandbox d'exécution Python (Phase 2)
    sandbox_image: str = "hybrid-data-analyst-sandbox:latest"
    sandbox_memory_limit: str = "512m"
    sandbox_cpu_limit: str = "1.0"
    sandbox_pids_limit: int = 128
    sandbox_timeout_seconds: int = 30
    # Chrome headless (kaleido, export PNG) a un démarrage plus variable que
    # du calcul pandas pur -> timeout par défaut plus généreux (Phase 3).
    sandbox_chart_timeout_seconds: int = 45

    log_level: str = "INFO"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_admin_dsn(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_admin_user}:{self.postgres_admin_password}"
            f"@{self.postgres_host}:{self.postgres_port}/postgres"
        )

    @property
    def postgres_readonly_dsn(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_readonly_user}:{self.postgres_readonly_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
