from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "PeopleMatch Agent Backend"
    app_env: str = "development"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"

    postgres_host: Optional[str] = None
    postgres_port: Optional[int] = None
    postgres_db: Optional[str] = None
    postgres_user: Optional[str] = None
    postgres_password: Optional[str] = None
    database_url: Optional[str] = None

    redis_url: Optional[str] = None
    qdrant_url: Optional[str] = None
    next_public_api_base_url: Optional[str] = None
    cors_origins: str = "http://localhost:3000"
    llm_api_key: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> List[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def required_database_url(self) -> str:
        if not self.database_url:
            raise RuntimeError("DATABASE_URL must be configured for persistence operations")
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
