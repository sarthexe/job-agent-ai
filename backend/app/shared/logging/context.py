"""Contextual logging helpers built on structlog contextvars.

Use these to attach context to every log line emitted from a scope —
HTTP requests (done automatically by ``RequestIDMiddleware``), background
workers, and agent runs::

    from app.shared.logging import bind, clear, request_context

    with request_context():          # generates and binds a request_id
        bind(job_id="abc")
        ...
        clear()                      # or let the scope end

Workers that carry their own correlation id can pass it explicitly:
``request_context(request_id=...)``.
"""

from __future__ import annotations

import contextlib
import contextvars
import uuid
from collections.abc import Iterator

import structlog
import structlog.contextvars

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


def bind(**kwargs: object) -> None:
    """Bind key/value pairs to the current logging context."""
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind(*keys: str) -> None:
    """Remove the given keys from the current logging context."""
    structlog.contextvars.unbind_contextvars(*keys)


def clear() -> None:
    """Clear all bound context for the current context."""
    structlog.contextvars.clear_contextvars()


def get_request_id() -> str:
    """Return the request_id active in the current context ("" if none)."""
    return request_id_var.get()


@contextlib.contextmanager
def request_context(request_id: str | None = None) -> Iterator[str]:
    """Bind a request_id for the duration of the block and yield it.

    Generates a UUID when no request_id is given. The context (including
    the structlog binding) is restored on exit, so nested scopes compose.
    """
    resolved = request_id or uuid.uuid4().hex
    token = request_id_var.set(resolved)
    bind(request_id=resolved)
    try:
        yield resolved
    finally:
        unbind("request_id")
        request_id_var.reset(token)
