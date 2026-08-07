"""Domain exception hierarchy and FastAPI error handling.

All domain errors inherit from :class:`AppError` and carry an HTTP
``status_code`` plus a stable machine-readable ``code``. Register
:class:`AppError` with a FastAPI ``exception_handler`` (see
``app.main``) so domain failures become meaningful HTTP responses
instead of generic 500s.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for all domain errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    """Requested resource does not exist."""

    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    """Request conflicts with the current state of the resource."""

    status_code = 409
    code = "conflict"


class DuplicateError(ConflictError):
    """A resource with the same identity already exists."""

    code = "duplicate"


class InvalidStatusTransitionError(ConflictError):
    """A resource state change violates the allowed transition rules."""

    code = "invalid_status_transition"


class JobAlreadyAppliedError(ConflictError):
    """An action requires an unapplied job, but the job is already applied."""

    code = "job_already_applied"


class DomainValidationError(AppError):
    """Input violates a domain rule (distinct from pydantic schema errors)."""

    status_code = 422
    code = "validation_error"


__all__ = [
    "AppError",
    "ConflictError",
    "DomainValidationError",
    "DuplicateError",
    "InvalidStatusTransitionError",
    "JobAlreadyAppliedError",
    "NotFoundError",
]
