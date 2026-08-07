"""Shared AI infrastructure.

The provider-agnostic platform every future feature (Jobs, Resume,
Applications, Interviews, Email, LangGraph workflows) consumes. Business
modules must never import provider SDKs (google-genai, anthropic,
openai, voyageai) directly — use the interfaces, factory, and prompt
manager exposed here.
"""

from app.shared.ai.exceptions import (
    AIAuthenticationError,
    AIConfigurationError,
    AIError,
    AINetworkError,
    AIProviderError,
    AIRateLimitError,
    AIResponseValidationError,
    AITimeoutError,
    PromptNotFoundError,
    PromptRenderError,
)
from app.shared.ai.factory import AIProviderFactory, factory, get_provider
from app.shared.ai.interfaces import AIProvider, EmbeddingProvider
from app.shared.ai.models import AIResponse, EmbeddingResult
from app.shared.ai.prompts import PromptLoader, PromptManager, manager
from app.shared.ai.usage import UsageRecord, UsageTracker, get_tracker

__all__ = [
    "AIAuthenticationError",
    "AIConfigurationError",
    "AIError",
    "AINetworkError",
    "AIProvider",
    "AIProviderError",
    "AIProviderFactory",
    "AIRateLimitError",
    "AIResponse",
    "AIResponseValidationError",
    "AITimeoutError",
    "EmbeddingProvider",
    "EmbeddingResult",
    "PromptLoader",
    "PromptManager",
    "PromptNotFoundError",
    "PromptRenderError",
    "UsageRecord",
    "UsageTracker",
    "factory",
    "get_provider",
    "get_tracker",
    "manager",
]
