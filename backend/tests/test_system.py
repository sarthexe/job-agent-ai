"""Tests for the system feature (root, health, readiness, liveness, version, metrics)."""

import os
import platform
import re
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.shared.config import settings
from app.system import repository, service
from app.system.repository import check_postgresql as real_check_postgresql
from app.system.schemas import ServiceHealth

client = TestClient(app)


async def _ok() -> ServiceHealth:
    return ServiceHealth(status="ok", latency_ms=0.5)


async def _down() -> ServiceHealth:
    return ServiceHealth(status="unavailable", latency_ms=0.5)


@pytest.fixture(autouse=True)
def _healthy_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default: every dependency probe reports healthy."""
    monkeypatch.setattr(repository, "check_postgresql", _ok)
    monkeypatch.setattr(repository, "check_redis", _ok)
    monkeypatch.setattr(repository, "check_qdrant", _ok)


# --- root -------------------------------------------------------------------


def test_root_returns_service_identification() -> None:
    response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == settings.app.name
    assert body["version"] == settings.app.version
    assert body["docs"] == "/docs"


# --- liveness ----------------------------------------------------------------


def test_live_returns_alive() -> None:
    response = client.get("/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


# --- health and readiness ----------------------------------------------------


def test_health_reports_all_services_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["services"]) == {"postgresql", "redis", "qdrant"}
    for service_health in body["services"].values():
        assert service_health["status"] == "ok"
        assert service_health["latency_ms"] >= 0


def test_health_returns_503_when_dependency_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(repository, "check_postgresql", _down)

    response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["services"]["postgresql"]["status"] == "unavailable"
    assert body["services"]["redis"]["status"] == "ok"


def test_ready_returns_200_when_all_dependencies_available() -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_returns_503_when_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(repository, "check_qdrant", _down)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["services"]["qdrant"]["status"] == "unavailable"


# --- version ----------------------------------------------------------------


def test_version_exposes_expected_fields() -> None:
    response = client.get("/version")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == settings.app.name
    assert body["version"] == settings.app.version
    assert body["environment"] == settings.app.environment
    assert body["python_version"] == platform.python_version()
    assert body["git_commit"] is None or re.fullmatch(
        r"[0-9a-f]{7,40}", body["git_commit"]
    )
    datetime.fromisoformat(body["startup_time"])  # must parse
    assert body["uptime_seconds"] >= 0


# --- metrics ----------------------------------------------------------------


def test_metrics_exposes_process_and_runtime_stats() -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    body = response.json()
    assert body["metrics_version"] == 1
    assert body["process"]["pid"] == os.getpid()
    assert body["process"]["memory_rss_bytes"] > 0
    assert body["process"]["cpu_percent"] >= 0
    assert body["process"]["threads"] >= 1
    assert body["process"]["uptime_seconds"] >= 0
    assert body["runtime"]["python_version"] == platform.python_version()
    datetime.fromisoformat(body["runtime"]["startup_time"])
    assert body["custom"] == {}


def test_metrics_includes_registered_providers() -> None:
    service.register_metric_provider("test_counter", lambda: {"value": 42})
    try:
        response = client.get("/metrics")
    finally:
        service._metric_providers.pop("test_counter", None)

    assert response.status_code == 200
    assert response.json()["custom"] == {"test_counter": {"value": 42}}


# --- repository probes ------------------------------------------------------


async def test_postgresql_probe_reports_ok_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeConnection:
        async def execute(self, _statement: object) -> None:
            return None

    class FakeContext:
        async def __aenter__(self) -> FakeConnection:
            return FakeConnection()

        async def __aexit__(self, *args: object) -> bool:
            return False

    class FakeEngine:
        def connect(self) -> FakeContext:
            return FakeContext()

    monkeypatch.setattr(repository, "get_engine", lambda: FakeEngine())

    # The autouse fixture patches check_postgresql; use the real function,
    # which resolves get_engine() from the (patched) module namespace.
    result = await real_check_postgresql()

    assert result.status == "ok"
    assert result.latency_ms >= 0


async def test_postgresql_probe_reports_unavailable_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingContext:
        async def __aenter__(self) -> None:
            raise RuntimeError("connection refused")

        async def __aexit__(self, *args: object) -> bool:
            return False

    class FailingEngine:
        def connect(self) -> FailingContext:
            return FailingContext()

    monkeypatch.setattr(repository, "get_engine", lambda: FailingEngine())

    result = await real_check_postgresql()

    assert result.status == "unavailable"
    assert result.latency_ms >= 0
