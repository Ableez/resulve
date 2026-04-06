from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="RESULVE_", extra="ignore")

    database_url: str = "postgresql+asyncpg://resulve:resulve@localhost:5432/resulve"
    database_url_sync: str = "postgresql+psycopg2://resulve:resulve@localhost:5432/resulve"

    redis_url: str = "redis://localhost:6379/0"

    s3_bucket: str = "resulve-artifacts"
    s3_region: str = "us-east-1"
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None

    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    embedding_batch_size: int = 100

    webhook_secret: str = "changeme"

    layout_k: float = 1.0
    layout_iterations: int = 60

    bulk_hnsw_ef: int = 40
    query_hnsw_ef: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()
