"""structlog configuration and the shared logger interface.

Every agent, workflow, and worker obtains loggers through
:func:`get_logger` — never create loggers or read logging settings
directly::

    from app.shared.logging import get_logger

    logger = get_logger(__name__)
    logger.info("job_discovered", job_id="abc", source="linkedin")
    logger.error("apply_failed", job_id="abc", exc_info=True)

Call :func:`setup_logging` once at process startup (the FastAPI app in
``app.main`` does this automatically). Renderer selection follows the
centralized settings: development defaults to pretty console output,
staging and production default to JSON lines; an explicit
``LOGGING_FORMAT`` always wins. Every record includes a timestamp,
log level, logger (module) name, event, any bound context (including
``request_id`` inside HTTP requests), and execution timing where the
:func:`~app.shared.logging.log_execution` helper is used.
"""

from __future__ import annotations

import logging
import sys

import structlog
import structlog.contextvars
from structlog.stdlib import ProcessorFormatter
from structlog.typing import Processor

from app.shared.config.settings import LoggingSettings, Settings

_configured = False
_handler: logging.Handler | None = None


def resolve_renderer(logging_settings: LoggingSettings, environment: str) -> Processor:
    """Pick the output renderer for the given logging settings and environment.

    Explicit ``LOGGING_FORMAT=text`` always renders pretty console output;
    explicit ``json`` always renders JSON. When the format is not explicitly
    configured, development defaults to the console renderer and every other
    environment defaults to JSON.
    """
    format_explicitly_set = "format" in logging_settings.model_fields_set
    if logging_settings.format == "text" or (
        not format_explicitly_set and environment == "development"
    ):
        return structlog.dev.ConsoleRenderer()
    return structlog.processors.JSONRenderer()


def _build_shared_processors() -> list[Processor]:
    """Return the processors shared by structlog and foreign (stdlib) records."""
    return [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
    ]


def setup_logging(settings: Settings, *, force: bool = False) -> None:
    """Configure structlog and the stdlib logging root once per process.

    Idempotent: subsequent calls are no-ops unless ``force=True`` (used by
    tests to reconfigure). Third-party logs (e.g. uvicorn) flow through the
    same formatter; uvicorn's own access logger is silenced in favour of
    :class:`~app.shared.logging.middleware.RequestIDMiddleware` access logs.
    """
    global _configured, _handler

    if _configured and not force:
        return

    renderer = resolve_renderer(settings.logging, settings.app.environment)
    shared_processors = _build_shared_processors()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = ProcessorFormatter(
        processors=[
            ProcessorFormatter.remove_processors_meta,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        foreign_pre_chain=[
            *shared_processors,
            structlog.processors.format_exc_info,
        ],
    )

    root = logging.getLogger()
    if _handler is not None:
        root.removeHandler(_handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(settings.logging.level.upper())
    _handler = handler
    _configured = True

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger for the calling module.

    Pass ``__name__`` so log records carry the module (logger) name.
    """
    return structlog.get_logger(name)
