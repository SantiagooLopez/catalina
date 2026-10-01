from functools import lru_cache
from pathlib import Path
from typing import Literal

from psycopg.conninfo import make_conninfo
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Catalina Ingestion Service"
    app_env: Literal["development", "testing", "production"] = "development"
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8001, ge=1, le=65535)
    log_level: str = "INFO"
    auth_jwt_secret: str | None = Field(
        default=None,
        min_length=32,
        repr=False,
    )
    auth_jwt_algorithm: Literal["HS256"] = "HS256"
    auth_access_token_minutes: int = Field(
        default=15,
        ge=1,
        le=1440,
    )
    auth_refresh_token_days: int = Field(
        default=7,
        ge=1,
        le=90,
    )
    auth_jwt_issuer: str = Field(
        default="catalina-api",
        min_length=1,
        max_length=100,
    )
    auth_jwt_audience: str = Field(
        default="catalina-web",
        min_length=1,
        max_length=100,
    )
    database_host: str = "127.0.0.1"
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = "catalina_db"
    database_user: str = "catalina_user"
    database_password: str = Field(repr=False, min_length=12)
    database_min_pool_size: int = Field(default=1, ge=1)
    database_max_pool_size: int = Field(default=5, ge=1)
    database_connect_timeout: int = Field(default=10, ge=1)

    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_collection: str = "documentos_universidad"
    qdrant_timeout_seconds: int = Field(default=30, ge=1)
    qdrant_upsert_batch_size: int = Field(
        default=64,
        ge=1,
        le=1000,
    )

    ollama_url: str = "http://127.0.0.1:11434"

    ollama_embedding_model: str = "embeddinggemma:latest"
    ollama_generation_model: str = "llama3.2:3b"

    ollama_timeout_seconds: int = Field(default=120, ge=1)
    ollama_keep_alive: str = "10m"

    generation_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
    )
    generation_max_tokens: int = Field(
        default=512,
        ge=1,
        le=4096,
    )
    generation_retry_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
    )
    generation_retry_wait_seconds: float = Field(
        default=1.0,
        ge=0.0,
        le=30.0,
    )

    embedding_dimension: int = Field(default=768, gt=0)
    embedding_batch_size: int = Field(default=8, ge=1)
    ollama_truncate: bool = False
    embedding_retry_attempts: int = Field(default=3, ge=1, le=10)
    embedding_retry_wait_seconds: float = Field(
        default=1,
        ge=0,
        le=30,
    )

    documents_root: Path = Path("/opt/catalina/documents")
    staging_directory: Path = Path("/opt/catalina/documents/staging")
    quarantine_directory: Path = Path("/opt/catalina/documents/quarantine")
    max_file_size_mb: int = Field(default=50, ge=1)

    allowed_extensions: list[str] = [
        ".pdf",
        ".docx",
        ".txt",
        ".html",
        ".htm",
    ]

    allowed_mime_types: list[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/html",
    ]

    allowed_categories: list[str] = [
        "reglamentos",
        "academico",
        "administrativo",
        "bienestar",
        "sedes",
        "facultades",
        "faq",
        "historico",
    ]

    chunk_target_size: int = Field(default=500, ge=1)
    chunk_overlap: int = Field(default=80, ge=0)
    chunk_min_size: int = Field(default=80, ge=1)

    worker_poll_seconds: int = Field(default=3, ge=1)
    worker_max_attempts: int = Field(default=3, ge=1)

    @field_validator("allowed_extensions")
    @classmethod
    def normalize_extensions(cls, values: list[str]) -> list[str]:
        return [value.lower() if value.startswith(".") else f".{value.lower()}" for value in values]

    @field_validator("allowed_categories")
    @classmethod
    def normalize_categories(cls, values: list[str]) -> list[str]:
        return [value.lower().strip() for value in values]

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        normalized = value.upper()

        if normalized not in valid_levels:
            raise ValueError(f"Nivel de log inválido: {value}")

        return normalized

    @property
    def database_conninfo(self) -> str:
        return make_conninfo(
            host=self.database_host,
            port=self.database_port,
            dbname=self.database_name,
            user=self.database_user,
            password=self.database_password,
            connect_timeout=self.database_connect_timeout,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
