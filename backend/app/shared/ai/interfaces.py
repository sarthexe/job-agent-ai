"""Provider-agnostic AI interfaces.

Business modules depend on :class:`AIProvider` and
:class:`EmbeddingProvider` — never on provider SDKs directly. Every
provider wrapper implements the exact same async surface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import ClassVar

from app.shared.ai.models import AIResponse, EmbeddingResult


class AIProvider(ABC):
    """Contract implemented by every LLM provider wrapper."""

    provider_name: ClassVar[str] = ""
    default_model: ClassVar[str] = ""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AIResponse:
        """Generate text for ``prompt`` and return a normalized response."""

    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AIResponse:
        """Generate text and validate that it parses as JSON.

        The parsed object is stored in ``AIResponse.metadata["parsed"]``.
        Raises :class:`AIResponseValidationError` on invalid JSON.
        """

    @abstractmethod
    def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Yield response text chunks as they arrive."""

    @abstractmethod
    async def health(self) -> bool:
        """Return True when the provider is reachable and authenticated."""

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """Estimate the token count of ``text`` for this provider."""

    @abstractmethod
    async def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate the USD cost of a request for this provider's model."""


class EmbeddingProvider(ABC):
    """Contract implemented by embedding providers."""

    provider_name: ClassVar[str] = ""
    default_model: ClassVar[str] = ""

    @abstractmethod
    async def embed_text(self, text: str) -> EmbeddingResult:
        """Embed a single text and return a typed result."""

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """Embed many texts in a single provider request."""

    @abstractmethod
    async def health(self) -> bool:
        """Return True when the provider is reachable and authenticated."""

    @abstractmethod
    async def estimate_cost(self, tokens: int) -> float:
        """Estimate the USD cost of embedding ``tokens`` tokens."""


__all__ = ["AIProvider", "EmbeddingProvider"]
