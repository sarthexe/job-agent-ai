"""Shared fixtures for the test suite."""

from __future__ import annotations

from pydantic import SecretStr

from app.shared.config.settings import AiSettings, Settings

_DEFAULT_AI_KEYS = {
    "gemini_api_key": "gemini-test-key",
    "anthropic_api_key": "anthropic-test-key",
    "openai_api_key": "openai-test-key",
    "voyage_api_key": "voyage-test-key",
}


def make_ai_settings(**overrides: object) -> Settings:
    """Build a Settings instance with test AI keys (no .env access)."""
    kwargs = {key: SecretStr(value) for key, value in _DEFAULT_AI_KEYS.items()}
    kwargs.update(overrides)
    return Settings(
        _env_file=None,
        ai=AiSettings(_env_file=None, **kwargs),
    )
