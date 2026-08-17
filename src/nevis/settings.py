from functools import lru_cache
from typing import Literal, cast

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NEVIS_", extra="ignore")

    environment: Literal["local", "test", "production"] = "local"
    identity_provider: Literal["local-header", "deterministic", "oidc"] | None = None
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_algorithms: tuple[str, ...] = ("RS256",)
    oidc_token_max_length: int = Field(default=16_384, ge=256, le=65_536)
    oidc_subject_max_length: int = Field(default=200, ge=1, le=500)
    oidc_clock_skew_seconds: int = Field(default=30, ge=0, le=300)
    oidc_jwks_fresh_ttl_seconds: int = Field(default=900, ge=30, le=86_400)
    oidc_jwks_max_stale_seconds: int = Field(default=86_400, ge=60, le=604_800)
    oidc_jwks_refresh_min_interval_seconds: int = Field(default=30, ge=1, le=3_600)
    oidc_http_timeout_seconds: float = Field(default=5.0, ge=0.25, le=30.0)
    oidc_response_max_bytes: int = Field(default=1_048_576, ge=1_024, le=5_242_880)
    database_url: str = "postgresql+asyncpg://nevis:nevis@localhost:5432/nevis"
    embedding_provider: str = "tei"
    tei_base_url: str = Field(default="http://localhost:8080")
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_model_revision: str = "5c38ec7"
    embedding_dimensions: int = Field(default=384, gt=0)
    embedding_normalization: str = "l2"
    embedding_chunking_version: int = Field(default=1, ge=1)
    embedding_pipeline_version: int = Field(default=1, ge=1)
    reranker_provider: str = "tei"
    reranker_base_url: str = "http://localhost:8081"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    reranker_model_revision: str = "c5ee24c"
    reranker_timeout_seconds: float = Field(default=1.0, ge=0.1, le=30.0)
    log_level: str = "INFO"
    search_query_max_length: int = Field(default=500, ge=1, le=2_000)
    search_default_limit: int = Field(default=20, ge=1, le=100)
    search_max_limit: int = Field(default=50, ge=1, le=200)
    search_lexical_candidates: int = Field(default=100, ge=1, le=1_000)
    search_semantic_candidates: int = Field(default=100, ge=1, le=1_000)
    search_client_candidates: int = Field(default=100, ge=1, le=1_000)
    search_client_description_excerpt_length: int = Field(default=180, ge=20, le=1_000)
    search_client_weight: float = Field(default=1.0, gt=0.0, le=10.0)
    search_document_lexical_weight: float = Field(default=1.0, gt=0.0, le=10.0)
    search_document_semantic_weight: float = Field(default=1.0, gt=0.0, le=10.0)
    search_ranking_version: Literal["mixed-rrf-v1"] = "mixed-rrf-v1"
    search_semantic_threshold: float = Field(default=0.70, ge=-1.0, le=1.0)
    search_rrf_version: int = Field(default=1, ge=1)
    search_rrf_constant: int = Field(default=60, ge=1, le=1_000)
    search_snippet_length: int = Field(default=280, ge=40, le=2_000)
    search_cursor_ttl_seconds: int = Field(default=900, ge=60, le=86_400)
    search_cursor_signing_key: str = "nevis-local-cursor-signing-key-change-me"

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        if self.search_default_limit > self.search_max_limit:
            raise ValueError("search_default_limit must not exceed search_max_limit")
        if self.environment == "production" and (
            self.search_cursor_signing_key == "nevis-local-cursor-signing-key-change-me"
            or len(self.search_cursor_signing_key) < 32
        ):
            raise ValueError("a strong search cursor signing key is required outside local/test")
        expected_provider = cast(
            Literal["local-header", "deterministic", "oidc"],
            {
                "local": "local-header",
                "test": "deterministic",
                "production": "oidc",
            }[self.environment],
        )
        if self.identity_provider is None:
            self.identity_provider = expected_provider
        if self.identity_provider != expected_provider:
            raise ValueError(
                f"identity provider {self.identity_provider!r} is not allowed in {self.environment}"
            )
        if self.oidc_jwks_max_stale_seconds < self.oidc_jwks_fresh_ttl_seconds:
            raise ValueError("OIDC maximum stale window must not be shorter than fresh TTL")
        if self.environment == "production":
            if not self.oidc_issuer or not self.oidc_issuer.startswith("https://"):
                raise ValueError("a HTTPS OIDC issuer is required in production")
            self.oidc_issuer = self.oidc_issuer.rstrip("/")
            if not self.oidc_audience or not self.oidc_audience.strip():
                raise ValueError("an OIDC audience is required in production")
            if not self.oidc_algorithms or set(self.oidc_algorithms) != {"RS256"}:
                raise ValueError("production OIDC algorithms must be exactly RS256")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
