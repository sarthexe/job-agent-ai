"""Shared structured logging infrastructure for the job agent platform.

This is the logging interface every agent, workflow, and worker must use::

    from app.shared.logging import get_logger

    logger = get_logger(__name__)
    logger.info("job_discovered", job_id="abc", source="linkedin")

Call :func:`setup_logging` once at process startup — ``app.main`` does this
automatically. Development renders pretty console output; staging and
production render JSON lines (see ``settings.logging``). Every record
carries a timestamp, level, module, event, and any bound context.

Contextual helpers: :func:`bind`, :func:`unbind`, :func:`clear`,
:func:`request_context`, :func:`get_request_id`.
Timing helpers: :func:`log_execution`, :func:`timed`.
HTTP integration: :class:`RequestIDMiddleware`.
"""

from app.shared.logging.context import (
    bind,
    clear,
    get_request_id,
    request_context,
    request_id_var,
    unbind,
)
from app.shared.logging.helpers import log_execution, timed
from app.shared.logging.middleware import REQUEST_ID_HEADER, RequestIDMiddleware
from app.shared.logging.setup import get_logger, resolve_renderer, setup_logging

__all__ = [
    "REQUEST_ID_HEADER",
    "RequestIDMiddleware",
    "bind",
    "clear",
    "get_logger",
    "get_request_id",
    "log_execution",
    "request_context",
    "request_id_var",
    "resolve_renderer",
    "setup_logging",
    "timed",
    "unbind",
]
