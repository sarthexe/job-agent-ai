"""Tests for the shared structured logging infrastructure."""

import logging as stdlib_logging

import pytest
import structlog
import structlog.testing
from fastapi import FastAPI
from fastapi.testclient import TestClient
from structlog.stdlib import ProcessorFormatter

from app.shared.config import Settings
from app.shared.config.settings import LoggingSettings
from app.shared.logging import (
    REQUEST_ID_HEADER,
    RequestIDMiddleware,
    bind,
    clear,
    get_logger,
    get_request_id,
    log_execution,
    request_context,
    resolve_renderer,
    setup_logging,
)
from app.shared.logging.context import request_id_var


@pytest.fixture(scope="module", autouse=True)
def _configure_logging() -> None:
    """Configure structlog once so get_logger() returns real bound loggers."""
    setup_logging(Settings(_env_file=None), force=True)


@pytest.fixture(autouse=True)
def _clean_logging_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep logging-related env vars out of every test."""
    monkeypatch.delenv("LOGGING_FORMAT", raising=False)
    monkeypatch.delenv("LOGGING_LEVEL", raising=False)
    monkeypatch.delenv("APP_ENVIRONMENT", raising=False)


def _new_settings() -> Settings:
    return Settings(_env_file=None)


def test_get_logger_returns_bound_logger() -> None:
    # structlog 25.x returns a lazy proxy from get_logger(); it must behave
    # like a bound logger and emit through the configured pipeline.
    logger = get_logger("tests.logging")

    assert callable(logger.info)
    assert callable(logger.error)
    assert callable(logger.exception)

    with structlog.testing.capture_logs() as logs:
        logger.info("proxy_emits")

    assert logs[0]["event"] == "proxy_emits"


def test_renderer_defaults_to_console_in_development() -> None:
    logging_settings = LoggingSettings(_env_file=None)

    renderer = resolve_renderer(logging_settings, "development")

    assert isinstance(renderer, structlog.dev.ConsoleRenderer)


def test_renderer_defaults_to_json_outside_development() -> None:
    logging_settings = LoggingSettings(_env_file=None)

    assert isinstance(
        resolve_renderer(logging_settings, "staging"), structlog.processors.JSONRenderer
    )
    assert isinstance(
        resolve_renderer(logging_settings, "production"),
        structlog.processors.JSONRenderer,
    )


def test_renderer_explicit_format_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGGING_FORMAT", "text")
    text_settings = LoggingSettings(_env_file=None)
    assert isinstance(
        resolve_renderer(text_settings, "production"), structlog.dev.ConsoleRenderer
    )

    monkeypatch.setenv("LOGGING_FORMAT", "json")
    json_settings = LoggingSettings(_env_file=None)
    assert isinstance(
        resolve_renderer(json_settings, "development"),
        structlog.processors.JSONRenderer,
    )


def test_setup_logging_configures_structlog_and_is_idempotent() -> None:
    setup_logging(_new_settings(), force=True)
    setup_logging(_new_settings())

    assert structlog.is_configured()
    our_handlers = [
        handler
        for handler in stdlib_logging.getLogger().handlers
        if isinstance(handler, stdlib_logging.StreamHandler)
        and isinstance(handler.formatter, ProcessorFormatter)
    ]
    assert len(our_handlers) == 1


def test_context_helpers_bind_and_clear() -> None:
    # capture_logs() replaces the processor chain (no contextvars merge), so
    # assert against structlog's live context instead.
    assert structlog.contextvars.get_contextvars() == {}

    bind(request_id="rid-1", job_id="j-1")

    assert structlog.contextvars.get_contextvars()["request_id"] == "rid-1"
    assert structlog.contextvars.get_contextvars()["job_id"] == "j-1"

    clear()

    assert structlog.contextvars.get_contextvars() == {}


def test_request_context_sets_and_restores_request_id() -> None:
    assert get_request_id() == ""

    with request_context("rid-9") as rid:
        assert rid == "rid-9"
        assert get_request_id() == "rid-9"
        assert request_id_var.get() == "rid-9"

    assert get_request_id() == ""


def test_log_execution_logs_status_and_duration() -> None:
    with structlog.testing.capture_logs() as logs:
        logger = get_logger("tests.logging")
        with log_execution(logger, "work", job_id="j-1"):
            pass

    assert logs[0]["event"] == "work.started"
    assert logs[0]["status"] == "started"
    assert logs[1]["event"] == "work"
    assert logs[1]["status"] == "success"
    assert logs[1]["execution_time_ms"] >= 0
    assert logs[1]["job_id"] == "j-1"


def test_log_execution_reports_errors_and_reraises() -> None:
    with (
        structlog.testing.capture_logs() as logs,
        pytest.raises(RuntimeError, match="boom"),
    ):
        logger = get_logger("tests.logging")
        with log_execution(logger, "work"):
            raise RuntimeError("boom")

    error_log = logs[-1]
    assert error_log["event"] == "work"
    assert error_log["status"] == "error"
    assert error_log["execution_time_ms"] >= 0


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/echo")
    async def echo() -> dict[str, str]:
        get_logger("tests.http").info("echo_requested")
        return {
            "request_id": get_request_id(),
            "bound": structlog.contextvars.get_contextvars().get("request_id"),
        }

    return app


def test_middleware_assigns_request_id() -> None:
    client = TestClient(_make_app())

    response = client.get("/echo")

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER]
    assert response.json()["request_id"] == response.headers[REQUEST_ID_HEADER]
    assert response.json()["bound"] == response.headers[REQUEST_ID_HEADER]


def test_middleware_honors_incoming_request_id() -> None:
    client = TestClient(_make_app())

    response = client.get("/echo", headers={REQUEST_ID_HEADER: "client-provided"})

    assert response.headers[REQUEST_ID_HEADER] == "client-provided"
    assert response.json()["request_id"] == "client-provided"
    assert response.json()["bound"] == "client-provided"


def test_middleware_logs_request_completed() -> None:
    with structlog.testing.capture_logs() as logs:
        client = TestClient(_make_app())
        client.get("/echo", headers={REQUEST_ID_HEADER: "log-me"})

    # request_id binding is covered by the header/route tests and the live
    # boot check; capture_logs drops the contextvars merge processor.
    completed = [entry for entry in logs if entry["event"] == "request_completed"]
    assert len(completed) == 1
    assert completed[0]["method"] == "GET"
    assert completed[0]["path"] == "/echo"
    assert completed[0]["status_code"] == 200
    assert completed[0]["status"] == "success"
    assert completed[0]["execution_time_ms"] >= 0


def test_middleware_logs_request_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("kaboom")

    with structlog.testing.capture_logs() as logs:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/boom")

    assert response.status_code == 500
    failed = [entry for entry in logs if entry["event"] == "request_failed"]
    assert len(failed) == 1
    assert failed[0]["status"] == "error"
    assert failed[0]["path"] == "/boom"
