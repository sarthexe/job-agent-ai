"""Strongly typed models shared across the AI infrastructure."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field


class AIResponse(BaseModel):
    """A normalized response from any model provider.

    Every provider returns this exact shape; business modules never see
    provider SDK objects.
    """

    text: str = ""
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    latency_ms: float = 0.0
    finish_reason: str | None = None
    raw_response: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_tokens(self) -> int:
        """Total tokens consumed by the request."""
        return self.input_tokens + self.output_tokens


class EmbeddingResult(BaseModel):
    """A strongly typed embedding produced by the embedding provider."""

    embedding: list[float]
    model: str
    dimensions: int
    tokens_used: int = 0
    estimated_cost: float = 0.0
    latency_ms: float = 0.0
    provider: str = "voyage"
    metadata: dict[str, Any] = Field(default_factory=dict)


class UsageSummary(BaseModel):
    """Aggregated usage statistics across all recorded AI requests."""

    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    failed_requests: int = 0
    avg_latency_ms: float = 0.0
    per_provider: dict[str, ProviderUsageSummary] = Field(default_factory=dict)


class ProviderUsageSummary(BaseModel):
    """Per-provider usage statistics."""

    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    failed_requests: int = 0


__all__ = ["AIResponse", "EmbeddingResult", "ProviderUsageSummary", "UsageSummary"]
