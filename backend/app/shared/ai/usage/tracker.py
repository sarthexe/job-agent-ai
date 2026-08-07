"""In-memory usage tracking for AI requests.

The base provider records every request automatically; business modules
never call this directly. No persistence yet — records live in memory
for the process lifetime and can be summarized or reset.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.shared.ai.models import ProviderUsageSummary, UsageSummary


@dataclass(frozen=True)
class UsageRecord:
    """A single AI request's usage snapshot."""

    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    request_id: str | None = None
    success: bool = True
    error_type: str | None = None


class UsageTracker:
    """Memory-only collector of AI usage records."""

    def __init__(self) -> None:
        self._records: list[UsageRecord] = []

    def record(self, record: UsageRecord) -> None:
        """Record one usage entry."""
        self._records.append(record)

    def records(self) -> list[UsageRecord]:
        """Return a defensive copy of all records."""
        return list(self._records)

    def summary(self) -> UsageSummary:
        """Aggregate totals, averages, and per-provider breakdowns."""
        summary = UsageSummary()
        for record in self._records:
            summary.total_requests += 1
            summary.total_input_tokens += record.input_tokens
            summary.total_output_tokens += record.output_tokens
            summary.total_cost += record.estimated_cost
            summary.total_tokens = (
                summary.total_input_tokens + summary.total_output_tokens
            )
            summary.avg_latency_ms += record.latency_ms
            if not record.success:
                summary.failed_requests += 1
            provider = summary.per_provider.setdefault(
                record.provider, ProviderUsageSummary()
            )
            provider.requests += 1
            provider.input_tokens += record.input_tokens
            provider.output_tokens += record.output_tokens
            provider.total_cost += record.estimated_cost
            if not record.success:
                provider.failed_requests += 1
        if summary.total_requests:
            summary.avg_latency_ms = round(
                summary.avg_latency_ms / summary.total_requests, 3
            )
        return summary

    def reset(self) -> None:
        """Clear all recorded usage."""
        self._records.clear()

    def __len__(self) -> int:
        return len(self._records)


__all__ = ["UsageRecord", "UsageTracker"]
