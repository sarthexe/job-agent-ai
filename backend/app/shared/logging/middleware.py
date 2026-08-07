"""Request ID middleware for FastAPI.

Assigns a ``request_id`` to every HTTP request — generated as a UUID, or
honouring an incoming ``X-Request-ID`` header — binds it to the logging
context for the request's lifetime, echoes it back on the response, and
emits structured access logs (method, path, status, duration, request_id).
"""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.shared.logging.context import bind, clear, request_id_var
from app.shared.logging.setup import get_logger

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a request id to the request context, logs, and response."""

    def __init__(self, app: ASGIApp, header: str = REQUEST_ID_HEADER) -> None:
        super().__init__(app)
        self.header = header

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get(self.header) or uuid.uuid4().hex
        request_id_var.set(request_id)
        bind(request_id=request_id)
        logger = get_logger("app.http")
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except BaseException:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
                status="error",
                execution_time_ms=round(elapsed_ms, 3),
            )
            raise
        else:
            elapsed_ms = (time.perf_counter() - start) * 1000
            response.headers[self.header] = request_id
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                status="success",
                execution_time_ms=round(elapsed_ms, 3),
            )
            return response
        finally:
            clear()
