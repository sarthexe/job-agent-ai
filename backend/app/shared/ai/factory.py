"""AI provider factory.

The rest of the application must never instantiate providers directly —
always go through :func:`get_provider`. Providers are registered by name
and built with the centralized settings, shared logger, and usage
tracker.
"""

from __future__ import annotations

from app.shared.ai.exceptions import AIConfigurationError
from app.shared.ai.interfaces import AIProvider
from app.shared.ai.providers import ClaudeProvider, GeminiProvider, GPTProvider
from app.shared.config import Settings, get_settings
from app.shared.logging import get_logger


class AIProviderFactory:
    """Registry and factory for LLM providers."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._logger = get_logger("app.shared.ai.factory")
        self._registry: dict[str, type[AIProvider]] = {
            "gemini": GeminiProvider,
            "claude": ClaudeProvider,
            "gpt": GPTProvider,
        }

    def register(self, name: str, provider_cls: type[AIProvider]) -> None:
        """Register (or replace) a provider implementation by name."""
        if not name or not name.isalnum():
            raise ValueError(f"invalid provider name: {name!r}")
        self._registry[name] = provider_cls

    def available(self) -> list[str]:
        """Return the names of all registered providers."""
        return sorted(self._registry)

    def configured(self) -> list[str]:
        """Return registered provider names whose API key is configured."""
        configured: list[str] = []
        for name in self.available():
            try:
                self.get_provider(name)
                configured.append(name)
            except AIConfigurationError:
                continue
        return configured

    def get_provider(self, name: str) -> AIProvider:
        """Build (or reuse) a provider instance by name.

        Raises :class:`AIConfigurationError` for unknown providers or
        providers whose API key is missing.
        """
        provider_cls = self._registry.get(name)
        if provider_cls is None:
            raise AIConfigurationError(
                f"unknown AI provider {name!r}; available: {self.available()}"
            )
        return provider_cls(settings=self._settings, logger=self._logger)


#: Process-wide factory; business modules import this singleton.
factory = AIProviderFactory()


def get_provider(name: str) -> AIProvider:
    """Return a provider instance for ``name`` (singleton factory)."""
    return factory.get_provider(name)


__all__ = ["AIProviderFactory", "factory", "get_provider"]
