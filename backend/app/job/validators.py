"""Domain validators for the Job feature.

These helpers implement the domain rules (salary ranges, URL shapes,
date ordering, and allowed status transitions) and raise the shared
domain exceptions. Pydantic schemas call them for field-level
validation; the service layer calls them for state-dependent rules such
as status transitions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse

from app.job.enums import JobStatus
from app.shared.exceptions import DomainValidationError, InvalidStatusTransitionError

SALARY_CURRENCY_LENGTH = 3


def validate_salary_range(
    salary_min: int | None,
    salary_max: int | None,
    salary_currency: str | None,
) -> None:
    """Validate a salary pair: both-or-neither, ordered, positive, currency shape.

    Raises :class:`DomainValidationError` when the rule is violated.
    """
    if (salary_min is None) != (salary_max is None):
        raise DomainValidationError(
            "salary_min and salary_max must be provided together"
        )
    if salary_min is not None and salary_max is not None:
        if salary_min < 0 or salary_max < 0:
            raise DomainValidationError("salary values must be non-negative")
        if salary_min > salary_max:
            raise DomainValidationError("salary_min must not exceed salary_max")
    if salary_currency is not None:
        if (
            len(salary_currency) != SALARY_CURRENCY_LENGTH
            or not salary_currency.isalpha()
        ):
            raise DomainValidationError(
                "salary_currency must be a 3-letter ISO 4217 code (e.g. USD)"
            )
        if salary_currency != salary_currency.upper():
            raise DomainValidationError("salary_currency must be uppercase")


def validate_url(value: str | None, *, field: str = "url") -> str | None:
    """Validate an http(s) URL; returns the trimmed value or None.

    Raises :class:`DomainValidationError` for non-http(s) or unparseable
    URLs.
    """
    if value is None:
        return None
    trimmed = value.strip()
    parsed = urlparse(trimmed)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise DomainValidationError(f"{field} must be a valid http(s) URL")
    return trimmed


def validate_dates(
    posted_at: datetime | None,
    expires_at: datetime | None,
) -> None:
    """Validate that a job's expiry is after its posting date."""
    if posted_at is not None and expires_at is not None and expires_at < posted_at:
        raise DomainValidationError("expires_at must not be before posted_at")


def normalize_currency(value: str | None) -> str | None:
    """Normalize a currency code to uppercase (or None)."""
    if value is None:
        return None
    return value.strip().upper()


def ensure_aware(value: datetime | None) -> datetime | None:
    """Stamp naive datetimes as UTC (the project's storage convention)."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


#: Allowed transitions between job lifecycle statuses. Staying in the
#: same status is always allowed (no-op updates).
STATUS_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.NEW: frozenset(
        {
            JobStatus.MATCHED,
            JobStatus.SHORTLISTED,
            JobStatus.APPLIED,
            JobStatus.REJECTED,
            JobStatus.ARCHIVED,
        }
    ),
    JobStatus.MATCHED: frozenset(
        {
            JobStatus.SHORTLISTED,
            JobStatus.APPLIED,
            JobStatus.REJECTED,
            JobStatus.ARCHIVED,
        }
    ),
    JobStatus.SHORTLISTED: frozenset(
        {JobStatus.APPLIED, JobStatus.REJECTED, JobStatus.ARCHIVED, JobStatus.MATCHED}
    ),
    JobStatus.APPLIED: frozenset(
        {JobStatus.INTERVIEW, JobStatus.REJECTED, JobStatus.ARCHIVED}
    ),
    JobStatus.INTERVIEW: frozenset(
        {JobStatus.OFFER, JobStatus.REJECTED, JobStatus.ARCHIVED}
    ),
    JobStatus.OFFER: frozenset({JobStatus.REJECTED, JobStatus.ARCHIVED}),
    JobStatus.REJECTED: frozenset(
        {JobStatus.ARCHIVED, JobStatus.NEW, JobStatus.MATCHED, JobStatus.SHORTLISTED}
    ),
    JobStatus.ARCHIVED: frozenset(
        {
            JobStatus.NEW,
            JobStatus.MATCHED,
            JobStatus.SHORTLISTED,
            JobStatus.APPLIED,
            JobStatus.REJECTED,
        }
    ),
}


def validate_status_transition(current: JobStatus, new: JobStatus) -> None:
    """Validate a status transition; same-status is always permitted.

    Raises :class:`InvalidStatusTransitionError` for disallowed moves.
    """
    if new == current:
        return
    if new not in STATUS_TRANSITIONS[current]:
        raise InvalidStatusTransitionError(
            f"invalid status transition: {current.value} -> {new.value}"
        )
