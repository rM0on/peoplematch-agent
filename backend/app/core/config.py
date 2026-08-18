from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field
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
    extraction_provider: str = "mock"
    extraction_max_attempts: int = Field(default=2, ge=1, le=2)
    extraction_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    retrieval_embedding_provider: str = "sentence_transformers"
    retrieval_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    retrieval_embedding_dimension: int = Field(default=384, gt=0)
    retrieval_candidate_collection: str = "peoplematch_candidates_retrieval_v1"
    retrieval_job_collection: str = "peoplematch_jobs_retrieval_v1"
    retrieval_rrf_k: int = Field(default=60, ge=1)
    retrieval_bm25_k1: float = Field(default=1.5, gt=0)
    retrieval_bm25_b: float = Field(default=0.75, ge=0, le=1)
    retrieval_pool_minimum: int = Field(default=20, ge=1)
    retrieval_pool_multiplier: int = Field(default=3, ge=1)
    ranking_model_path: str = str(PROJECT_ROOT / "artifacts" / "phase6" / "ltr_ranker_v1.txt")
    ranking_model_metadata_path: str = str(
        PROJECT_ROOT / "data" / "eval" / "phase6" / "ltr_model_metadata_v1.json"
    )
    cross_encoder_model_path: str = str(
        PROJECT_ROOT
        / "artifacts"
        / "phase7"
        / "cross_encoder_ms_marco_minilm_l6_v2"
    )
    cross_encoder_model_manifest_path: str = str(
        PROJECT_ROOT
        / "data"
        / "eval"
        / "phase7"
        / "cross_encoder_model_manifest_v1.json"
    )
    cross_encoder_text_contract_path: str = str(
        PROJECT_ROOT
        / "data"
        / "eval"
        / "phase7"
        / "cross_encoder_text_contract_v1.json"
    )
    cross_encoder_batch_size: int = Field(default=10, ge=1, le=50)

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
