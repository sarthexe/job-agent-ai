"""Project-specific exceptions for the shared AI infrastructure.

All AI errors subclass :class:`AppError` so the FastAPI exception handler
maps them to meaningful HTTP responses. ``retriable`` marks exceptions
that the retry layer (``app.shared.ai.retries``) is allowed to retry.
"""

from __future__ import annotations

from app.shared.exceptions import AppError


class AIError(AppError):
    """Base class for all AI infrastructure errors."""

    status_code = 502
    code = "ai_error"
    retriable = False


class AIProviderError(AIError):
    """The upstream model provider failed for a non-specific reason."""

    code = "ai_provider_error"


class AINetworkError(AIProviderError):
    """A transport-level failure occurred while reaching the provider."""

    code = "ai_network_error"
    retriable = True


class AIRateLimitError(AIProviderError):
    """The provider throttled the request; safe to retry with backoff."""

    status_code = 429
    code = "ai_rate_limit"
    retriable = True


class AITimeoutError(AIProviderError):
    """The provider did not answer within the configured timeout."""

    status_code = 504
    code = "ai_timeout"
    retriable = True


class AIAuthenticationError(AIProviderError):
    """The provider rejected the configured API key."""

    code = "ai_authentication"


class AIResponseValidationError(AIError):
    """The provider response did not match the expected shape (e.g. JSON)."""

    code = "ai_response_validation"


class AIConfigurationError(AIError):
    """The provider is not configured (e.g. missing API key or model)."""

    status_code = 500
    code = "ai_configuration"


class PromptNotFoundError(AIError):
    """A prompt template could not be found in the prompts directory."""

    status_code = 404
    code = "prompt_not_found"


class PromptRenderError(AIError):
    """A prompt template could not be rendered (e.g. undefined variable)."""

    code = "prompt_render"


def translate_sdk_error(exc: Exception) -> AIError:
    """Map a provider SDK exception to the project AI exception hierarchy.

    Works by exception class name and HTTP status code attributes so the
    base layer never needs to import provider SDKs.
    """
    name = type(exc).__name__
    status = getattr(exc, "status_code", None)
    message = str(exc) or name
    if "RateLimit" in name or "ResourceExhausted" in name or status == 429:
        return AIRateLimitError(message)
    if "Timeout" in name or isinstance(exc, TimeoutError):
        return AITimeoutError(message)
    if "Authentication" in name or "PermissionDenied" in name or status in (401, 403):
        return AIAuthenticationError(message)
    if any(
        token in name
        for token in ("Transport", "Connection", "Network", "APIConnection")
    ):
        return AINetworkError(message)
    return AIProviderError(message)


__all__ = [
    "AIAuthenticationError",
    "AIConfigurationError",
    "AIError",
    "AINetworkError",
    "AIProviderError",
    "AIRateLimitError",
    "AIResponseValidationError",
    "AITimeoutError",
    "PromptNotFoundError",
    "PromptRenderError",
    "translate_sdk_error",
]
