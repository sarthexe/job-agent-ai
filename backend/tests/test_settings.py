"""Tests for the centralized configuration system."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.shared.config import Settings
from app.shared.config.settings import (
    AiSettings,
    AppSettings,
    CorsSettings,
    DatabaseSettings,
    LoggingSettings,
    PlaywrightSettings,
    QdrantSettings,
    RedisSettings,
    SecuritySettings,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = BACKEND_DIR / ".env.example"

GROUP_MODELS = (
    AppSettings,
    SecuritySettings,
    DatabaseSettings,
    RedisSettings,
    QdrantSettings,
    AiSettings,
    PlaywrightSettings,
    LoggingSettings,
    CorsSettings,
)


def test_defaults_are_usable_without_env() -> None:
    fresh = Settings(_env_file=None)

    assert fresh.app.name == "jobagent"
    assert fresh.app.environment == "development"
    assert fresh.database.url.startswith("postgresql+asyncpg://")
    assert fresh.redis.url.startswith("redis://")
    assert fresh.ai.max_retries == 3
    assert fresh.cors.origins == ["http://localhost:3000", "http://127.0.0.1:3000"]


def test_environment_variables_override_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_NAME", "test-agent")
    monkeypatch.setenv("APP_DEBUG", "true")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/testdb"
    )
    monkeypatch.setenv("AI_GEMINI_API_KEY", "secret-key")

    fresh = Settings(_env_file=None)

    assert fresh.app.name == "test-agent"
    assert fresh.app.debug is True
    assert fresh.database.url == "postgresql+asyncpg://test:test@localhost:5432/testdb"
    assert fresh.ai.gemini_api_key.get_secret_value() == "secret-key"


def test_invalid_environment_value_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "mars")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_cors_origins_accepts_comma_separated_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a.example, http://b.example, ")

    cors = CorsSettings(_env_file=None)

    assert cors.origins == ["http://a.example", "http://b.example"]


def test_secrets_are_masked_in_json_dump(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECURITY_SECRET_KEY", "super-secret")
    monkeypatch.setenv("AI_GEMINI_API_KEY", "gemini-secret")

    dumped = Settings(_env_file=None).model_dump(mode="json")

    assert dumped["security"]["secret_key"] == "**********"
    assert dumped["ai"]["gemini_api_key"] == "**********"


def test_env_example_file_is_fully_loadable() -> None:
    # The root env_file is not propagated to nested group models, so each
    # group is validated directly against the example file.
    for model in GROUP_MODELS:
        parsed = model(_env_file=ENV_EXAMPLE)

        assert parsed is not None

    assert AppSettings(_env_file=ENV_EXAMPLE).environment == "development"
    assert LoggingSettings(_env_file=ENV_EXAMPLE).format == "json"
    assert CorsSettings(_env_file=ENV_EXAMPLE).origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    assert AiSettings(_env_file=ENV_EXAMPLE).gemini_api_key.get_secret_value() == ""
    assert DatabaseSettings(_env_file=ENV_EXAMPLE).url.startswith(
        "postgresql+asyncpg://"
    )
