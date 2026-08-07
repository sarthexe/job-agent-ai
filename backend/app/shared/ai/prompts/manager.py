"""Prompt manager: the business-facing entry point for prompts.

Wraps the loader with existence checks, version-aware lookups, and
structured logging. Future features and agents use ``manager.get`` /
``manager.render`` and never touch the filesystem.
"""

from __future__ import annotations

from typing import Any

from app.shared.ai.exceptions import PromptNotFoundError
from app.shared.ai.prompts.loader import PromptLoader
from app.shared.logging import get_logger


class PromptManager:
    """Registry-style access to prompt templates."""

    def __init__(self, loader: PromptLoader | None = None) -> None:
        self._loader = loader or PromptLoader()
        self._logger = get_logger("app.shared.ai.prompts")

    @property
    def loader(self) -> PromptLoader:
        return self._loader

    def get(self, name: str) -> str:
        """Return the raw template text for ``name``."""
        if not self._loader.exists(name):
            raise PromptNotFoundError(f"prompt {name!r} not found")
        return self._loader.load(name)

    def render(self, prompt_name: str, **context: Any) -> str:
        """Render ``prompt_name`` with the given Jinja2 context."""
        if not self._loader.exists(prompt_name):
            raise PromptNotFoundError(f"prompt {prompt_name!r} not found")
        rendered = self._loader.render(prompt_name, **context)
        self._logger.debug(
            "prompt_rendered", prompt=prompt_name, context_keys=list(context)
        )
        return rendered

    def exists(self, name: str) -> bool:
        """Return True when ``name`` resolves to a template file."""
        return self._loader.exists(name)

    def list_prompts(self) -> list[str]:
        """Return all available prompt names."""
        return self._loader.list_prompts()

    def versions(self, name: str) -> list[str]:
        """Return available versions of a prompt ('' for the base file)."""
        return self._loader.versions(name)


manager = PromptManager()


__all__ = ["PromptManager", "manager"]
