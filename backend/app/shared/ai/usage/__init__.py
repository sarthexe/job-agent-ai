"""Usage tracking for the AI infrastructure."""

from app.shared.ai.usage.tracker import UsageRecord, UsageTracker

#: Process-wide tracker; the base provider records into this singleton.
_tracker = UsageTracker()


def get_tracker() -> UsageTracker:
    """Return the process-wide usage tracker."""
    return _tracker


__all__ = ["UsageRecord", "UsageTracker", "get_tracker"]
