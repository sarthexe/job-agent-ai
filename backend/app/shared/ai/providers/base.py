"""Base class for LLM provider wrappers.

Owns the shared request pipeline: configuration validation, retry
policy, per-request timing, error translation, cost estimation, usage
recording, and structured logging. Concrete providers only implement the
SDK-specific bits (client creation, generate call, stream, health,
token counting) and never see the plumbing.
"""

from __future__ import annotations

import json
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, ClassVar

from app.shared.ai.exceptions import (
    AIConfigurationError,
    AIError,
    AIResponseValidationError,
    translate_sdk_error,
)
from app.shared.ai.interfaces import AIProvider
from app.shared.ai.models import AIResponse
from app.shared.ai.retries import RetryPolicy, with_retries
from app.shared.ai.usage import UsageRecord, UsageTracker, get_tracker
from app.shared.config import Settings, get_settings
from app.shared.logging import get_logger

_JSON_INSTRUCTION = "\n\nRespond with valid JSON only. No markdown, no prose."


class BaseAIProvider(AIProvider, ABC):
    """Shared implementation for all LLM provider wrappers."""

    provider_name: ClassVar[str] = ""
    default_model: ClassVar[str] = ""

    #: model name -> (input USD per 1M tokens, output USD per 1M tokens)
    PRICING: ClassVar[dict[str, tuple[float, float]]] = {}
    DEFAULT_PRICING: ClassVar[tuple[float, float]] = (1.0, 2.0)

    def __init__(
        self,
        settings: Settings | None = None,
        logger: Any | None = None,
        tracker: UsageTracker | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._logger = logger or get_logger(f"app.shared.ai.{self.provider_name}")
        self._tracker = tracker if tracker is not None else get_tracker()
        self._validate_configuration()
        self._client = self._create_client()

    # --- configuration hooks -------------------------------------------------

    @abstractmethod
    def _api_key(self) -> str:
        """Return the provider API key (empty when not configured)."""

    @abstractmethod
    def _model(self) -> str:
        """Return the configured model name for this provider."""

    @abstractmethod
    def _create_client(self) -> Any:
        """Build the provider SDK client (imported only in subclasses)."""

    @abstractmethod
    async def _call_generate(
        self,
        prompt: str,
        *,
        system: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> AIResponse:
        """Execute the provider's generate call and normalize the response."""

    # --- shared plumbing ------------------------------------------------------

    def _validate_configuration(self) -> None:
        if not self._api_key():
            raise AIConfigurationError(
                f"{self.provider_name} API key is not configured (see settings.ai)"
            )
        if not self._model():
            raise AIConfigurationError(
                f"{self.provider_name} model is not configured (see settings.ai)"
            )

    def _retry_policy(self) -> RetryPolicy:
        ai = self._settings.ai
        return RetryPolicy(
            max_retries=ai.max_retries,
            base_delay_seconds=ai.retry_base_delay_seconds,
            max_delay_seconds=ai.retry_max_delay_seconds,
            jitter=ai.retry_jitter,
            timeout_seconds=ai.timeout_seconds,
        )

    def _generate_operation(
        self,
        prompt: str,
        *,
        system: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> Callable[[], Awaitable[AIResponse]]:
        async def operation() -> AIResponse:
            try:
                return await self._call_generate(
                    prompt,
                    system=system,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except AIError:
                raise
            except Exception as exc:
                raise translate_sdk_error(exc) from exc

        return operation

    async def _run(self, operation: Callable[[], Awaitable[AIResponse]]) -> AIResponse:
        request_id = uuid.uuid4().hex
        started = time.perf_counter()
        try:
            response = await with_retries(
                operation, self._retry_policy(), self._logger, request_id=request_id
            )
        except AIError as exc:
            self._record_failure(exc, request_id, started)
            raise
        except Exception as exc:
            mapped = translate_sdk_error(exc)
            self._record_failure(mapped, request_id, started)
            raise mapped from exc

        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        response.latency_ms = latency_ms
        response.request_id = request_id
        response.estimated_cost = await self.estimate_cost(
            response.input_tokens, response.output_tokens
        )
        self._tracker.record(
            UsageRecord(
                provider=self.provider_name,
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                estimated_cost=response.estimated_cost,
                latency_ms=latency_ms,
                request_id=request_id,
            )
        )
        self._logger.info(
            "ai_request",
            provider=self.provider_name,
            model=response.model,
            execution_time_ms=latency_ms,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            estimated_cost=response.estimated_cost,
            finish_reason=response.finish_reason,
            request_id=request_id,
            status="success",
        )
        return response

    def _record_failure(self, exc: AIError, request_id: str, started: float) -> None:
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        self._tracker.record(
            UsageRecord(
                provider=self.provider_name,
                model=self._model(),
                latency_ms=latency_ms,
                request_id=request_id,
                success=False,
                error_type=type(exc).__name__,
            )
        )
        self._logger.warning(
            "ai_request",
            provider=self.provider_name,
            model=self._model(),
            execution_time_ms=latency_ms,
            request_id=request_id,
            status="error",
            error_type=type(exc).__name__,
            error=str(exc),
        )

    # --- AIProvider interface --------------------------------------------------

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AIResponse:
        """Generate text and return a normalized, tracked response."""
        return await self._run(
            self._generate_operation(
                prompt, system=system, temperature=temperature, max_tokens=max_tokens
            )
        )

    async def generate_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AIResponse:
        """Generate text and validate it parses as JSON.

        The parsed object is exposed as ``metadata["parsed"]``.
        """
        response = await self._run(
            self._generate_operation(
                f"{prompt}{_JSON_INSTRUCTION}",
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )
        try:
            parsed = json.loads(response.text)
        except json.JSONDecodeError as exc:
            self._logger.warning(
                "ai_response_validation_failed",
                provider=self.provider_name,
                model=response.model,
                request_id=response.request_id,
                error=str(exc),
            )
            raise AIResponseValidationError(
                f"{self.provider_name} returned invalid JSON: {exc}"
            ) from exc
        response.metadata["parsed"] = parsed
        return response

    async def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate USD cost using the provider pricing table."""
        input_price, output_price = self.PRICING.get(
            self._model(), self.DEFAULT_PRICING
        )
        return round(
            (input_tokens / 1_000_000) * input_price
            + (output_tokens / 1_000_000) * output_price,
            8,
        )

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


__all__ = ["BaseAIProvider"]
