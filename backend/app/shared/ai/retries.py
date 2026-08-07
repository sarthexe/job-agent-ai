"""Reusable retry utilities for outbound AI calls.

Exponential backoff with optional jitter, bounded by a configurable
maximum, honoring the project retry settings. Only retriable AI
exceptions (:class:`AIRateLimitError`, :class:`AITimeoutError`,
:class:`AINetworkError`) are retried; everything else propagates
immediately. Timeouts are enforced with ``asyncio.wait_for`` and surface
as :class:`AITimeoutError` (which is itself retriable).
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from app.shared.ai.exceptions import AIError, AITimeoutError

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    """Backoff configuration for retryable operations."""

    max_retries: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    jitter: bool = True
    timeout_seconds: float | None = None


async def with_retries(
    operation: Callable[[], Awaitable[T]],
    policy: RetryPolicy,
    logger: Any,
    *,
    request_id: str | None = None,
) -> T:
    """Run ``operation`` with exponential backoff and timeout enforcement.

    ``operation`` must be a no-argument awaitable factory. ``logger``
    only needs a ``warning`` method (structlog bound loggers qualify).
    """
    attempt = 0
    while True:
        try:
            if policy.timeout_seconds is not None:
                try:
                    return await asyncio.wait_for(operation(), policy.timeout_seconds)
                except TimeoutError:
                    raise AITimeoutError(
                        f"operation timed out after {policy.timeout_seconds}s"
                    ) from None
            return await operation()
        except AIError as exc:
            if not exc.retriable:
                raise
            attempt += 1
            if attempt > policy.max_retries:
                raise
            delay = min(
                policy.base_delay_seconds * (2 ** (attempt - 1)),
                policy.max_delay_seconds,
            )
            if policy.jitter:
                delay *= random.uniform(0.5, 1.5)
            logger.warning(
                "ai_retry",
                attempt=attempt,
                max_retries=policy.max_retries,
                delay_ms=round(delay * 1000, 1),
                error_type=type(exc).__name__,
                request_id=request_id,
            )
            await asyncio.sleep(delay)


__all__ = ["RetryPolicy", "with_retries"]
