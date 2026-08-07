"""Prompt template loading and rendering.

Templates live in ``backend/app/shared/prompts/`` as ``.md`` files.
Versioning is supported with the ``name@version`` convention, e.g.
``load("resume_tailor@v2")`` resolves ``resume_tailor_v2.md``.
Rendering uses Jinja2 with ``{{ variable }}`` placeholders.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    Template,
    UndefinedError,
)

from app.shared.ai.exceptions import PromptNotFoundError, PromptRenderError

#: Resolved to backend/app/shared/prompts unless overridden in tests.
DEFAULT_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"

_VERSION_PATTERN = re.compile(r"^(?P<name>.+?)@(?P<version>v\d+)$")


class PromptLoader:
    """Loads, caches, and renders prompt templates from disk."""

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self._prompts_dir = prompts_dir or DEFAULT_PROMPTS_DIR
        self._environment = Environment(
            loader=FileSystemLoader(str(self._prompts_dir)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            # Raise on missing variables instead of silently rendering "".
            undefined=StrictUndefined,
        )

    @property
    def prompts_dir(self) -> Path:
        return self._prompts_dir

    def exists(self, name: str) -> bool:
        """Return True when a template file exists for ``name``."""
        return self._resolve_filename(name) is not None

    def load(self, name: str) -> str:
        """Load and cache the raw template text for ``name``."""
        filename = self._resolve_filename(name)
        if filename is None:
            raise PromptNotFoundError(
                f"prompt {name!r} not found in {self._prompts_dir}"
            )
        return _read_file_cached(str(filename))

    def load_template(self, name: str) -> Template:
        """Load the Jinja2 template object for ``name``."""
        filename = self._resolve_filename(name)
        if filename is None:
            raise PromptNotFoundError(
                f"prompt {name!r} not found in {self._prompts_dir}"
            )
        return self._environment.get_template(filename.name)

    def render(self, prompt_name: str, **context: object) -> str:
        """Render ``prompt_name`` with the given Jinja2 context."""
        try:
            return self.load_template(prompt_name).render(**context)
        except UndefinedError as exc:
            raise PromptRenderError(
                f"prompt {prompt_name!r} references undefined variable: {exc}"
            ) from exc

    def versions(self, name: str) -> list[str]:
        """Return available version suffixes for a base name, e.g. ['', 'v2']."""
        found: list[str] = []
        for path in self._prompts_dir.glob(f"{name}*.md"):
            stem = path.stem
            if stem == name:
                found.append("")
            elif stem.startswith(f"{name}_v"):
                found.append(stem[len(name) + 1 :])
        return sorted(found)

    def list_prompts(self) -> list[str]:
        """Return all template file names (with version suffixes)."""
        return sorted(path.stem for path in self._prompts_dir.glob("*.md"))

    # --- internals ------------------------------------------------------------

    def _resolve_filename(self, name: str) -> Path | None:
        match = _VERSION_PATTERN.match(name)
        if match:
            filename = (
                self._prompts_dir / f"{match.group('name')}_{match.group('version')}.md"
            )
        else:
            filename = self._prompts_dir / f"{name}.md"
        return filename if filename.is_file() else None


@lru_cache(maxsize=256)
def _read_file_cached(filename: str) -> str:
    """Read a prompt file, cached by absolute path."""
    return Path(filename).read_text(encoding="utf-8")


__all__ = ["DEFAULT_PROMPTS_DIR", "PromptLoader"]
