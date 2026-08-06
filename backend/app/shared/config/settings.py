"""Centralized application settings.

All backend configuration is defined here and loaded from environment
variables and an optional ``.env`` file. Business logic must never read
``os.getenv()`` directly — import the ``settings`` singleton from
``app.shared.config`` instead.

Settings are grouped by domain (``AppSettings``, ``DatabaseSettings``, ...).
Each group reads its values from ``UPPER_CASE`` environment variables
prefixed with the group name, e.g. ``DATABASE_URL`` maps to
``DatabaseSettings.url``. See ``backend/.env.example`` for the full list.

Note: group models are attached to the root ``Settings`` via
``default_factory`` and declare their own ``env_file`` because
pydantic-settings >= 2.14 does not apply env sources to nested models
passed as instance defaults and does not propagate the root ``env_file``
to nested models.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["development", "staging", "production"]
LogFormat = Literal["json", "text"]


class AppSettings(BaseSettings):
    """General application settings."""

    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore"
    )

    name: str = "jobagent"
    environment: Environment = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8000


class SecuritySettings(BaseSettings):
    """Authentication and authorization settings."""

    model_config = SettingsConfigDict(
        env_prefix="SECURITY_", env_file=".env", extra="ignore"
    )

    #: Must be set to a strong random value in production.
    secret_key: SecretStr = SecretStr("")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection settings (SQLAlchemy async URL)."""

    model_config = SettingsConfigDict(
        env_prefix="DATABASE_", env_file=".env", extra="ignore"
    )

    url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/jobagent"
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False


class RedisSettings(BaseSettings):
    """Redis connection settings."""

    model_config = SettingsConfigDict(
        env_prefix="REDIS_", env_file=".env", extra="ignore"
    )

    url: str = "redis://localhost:6379/0"


class QdrantSettings(BaseSettings):
    """Qdrant vector store settings."""

    model_config = SettingsConfigDict(
        env_prefix="QDRANT_", env_file=".env", extra="ignore"
    )

    url: str = "http://localhost:6333"
    collection_name: str = "job_descriptions"
    embedding_dimensions: int = 1024


class AiSettings(BaseSettings):
    """LLM provider and embedding settings."""

    model_config = SettingsConfigDict(env_prefix="AI_", env_file=".env", extra="ignore")

    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-2.5-flash"
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model: str = "claude-sonnet-4-5"
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-5.5"
    voyage_api_key: SecretStr = SecretStr("")
    voyage_model: str = "voyage-3-large"
    timeout_seconds: float = 60.0
    max_retries: int = 3


class PlaywrightSettings(BaseSettings):
    """Browser automation settings for the Playwright workers."""

    model_config = SettingsConfigDict(
        env_prefix="PLAYWRIGHT_", env_file=".env", extra="ignore"
    )

    headless: bool = True
    timeout_ms: int = 30_000
    screenshots_dir: str = "artifacts/screenshots"
    storage_state_path: str | None = None


class LoggingSettings(BaseSettings):
    """Structured logging settings."""

    model_config = SettingsConfigDict(
        env_prefix="LOGGING_", env_file=".env", extra="ignore"
    )

    level: str = "INFO"
    format: LogFormat = "json"


class CorsSettings(BaseSettings):
    """CORS settings for the FastAPI application."""

    model_config = SettingsConfigDict(
        env_prefix="CORS_", env_file=".env", extra="ignore"
    )

    origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    allow_credentials: bool = True
    allow_methods: Annotated[list[str], NoDecode] = ["*"]
    allow_headers: Annotated[list[str], NoDecode] = ["*"]

    @field_validator("origins", "allow_methods", "allow_headers", mode="before")
    @classmethod
    def _parse_csv(cls, value: object) -> object:
        """Accept a JSON array or a comma-separated list from the environment."""
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return [item.strip() for item in value.split(",") if item.strip()]
            if isinstance(parsed, list):
                return parsed
        return value


class Settings(BaseSettings):
    """Root settings container grouping all configuration domains."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        frozen=True,
        extra="ignore",
    )

    app: AppSettings = Field(default_factory=AppSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    ai: AiSettings = Field(default_factory=AiSettings)
    playwright: PlaywrightSettings = Field(default_factory=PlaywrightSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    cors: CorsSettings = Field(default_factory=CorsSettings)


@lru_cache
def get_settings() -> Settings:
    """Return the application settings, constructed once and cached."""
    return Settings()


settings = get_settings()
