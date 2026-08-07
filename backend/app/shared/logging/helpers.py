"""Logging helpers for execution timing and status (AI_RULES logging rule).

Every log produced by these helpers includes ``execution_time_ms`` and
``status`` (``started`` / ``success`` / ``error``), plus the caller's
``event`` name. Errors re-raise after being logged with ``exc_info``.
"""

from __future__ import annotations

import contextlib
import functools
import inspect
import time
from collections.abc import Callable, Iterator
from typing import TypeVar

from structlog.stdlib import BoundLogger

from app.shared.logging.setup import get_logger

F = TypeVar("F", bound=Callable[..., object])


@contextlib.contextmanager
def log_execution(logger: BoundLogger, event: str, **fields: object) -> Iterator[None]:
    """Log a started/completed event pair around a block, with timing.

    On exception the block's error is logged (``status="error"``) and
    re-raised; otherwise ``status="success"``. Extra ``**fields`` are
    included in both records.
    """
    logger.info(f"{event}.started", status="started", **fields)
    start = time.perf_counter()
    try:
        yield
    except BaseException:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            event,
            status="error",
            execution_time_ms=round(elapsed_ms, 3),
            **fields,
        )
        raise
    else:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            event,
            status="success",
            execution_time_ms=round(elapsed_ms, 3),
            **fields,
        )


def timed(event: str, **fields: object) -> Callable[[F], F]:
    """Decorate a sync or async function to log its execution via log_execution.

    The function's module and qualified name are attached automatically::

        @timed("resume.tailored")
        async def tailor_resume(...) -> ...:
            ...
    """

    def decorator(fn: F) -> F:
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: object, **kwargs: object) -> object:
                logger = get_logger(fn.__module__)
                with log_execution(logger, event, function=fn.__qualname__, **fields):
                    return await fn(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def wrapper(*args: object, **kwargs: object) -> object:
            logger = get_logger(fn.__module__)
            with log_execution(logger, event, function=fn.__qualname__, **fields):
                return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
