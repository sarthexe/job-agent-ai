"""Tests for the AI infrastructure: exceptions, retries, prompts, usage tracking, factory."""

import asyncio
from pathlib import Path

import pytest

from app.shared.ai.exceptions import (
    AIConfigurationError,
    AIError,
    AIProviderError,
    AIRateLimitError,
    AITimeoutError,
    PromptNotFoundError,
    PromptRenderError,
    translate_sdk_error,
)
from app.shared.ai.factory import AIProviderFactory
from app.shared.ai.prompts import PromptLoader, PromptManager, manager
from app.shared.ai.providers import ClaudeProvider, GeminiProvider, GPTProvider
from app.shared.ai.retries import RetryPolicy, with_retries
from app.shared.ai.usage import UsageRecord, UsageTracker
from tests.conftest import make_ai_settings

# --- exceptions --------------------------------------------------------------


def test_ai_exception_hierarchy() -> None:
    assert issubclass(AIRateLimitError, AIProviderError)
    assert issubclass(AIProviderError, AIError)
    assert issubclass(AIError, Exception)
    assert AIRateLimitError.status_code == 429
    assert AITimeoutError.status_code == 504
    assert AIRateLimitError.retriable is True
    assert AITimeoutError.retriable is True
    assert AIProviderError.retriable is False
    error = AIRateLimitError("slow down")
    assert error.message == "slow down"
    assert error.code == "ai_rate_limit"


def test_translate_sdk_error_mappings() -> None:
    class FakeRateLimit(Exception):
        status_code = 429

    class FakeTimeout(Exception):
        pass

    class FakeAuth(Exception):
        status_code = 401

    class FakeConnection(Exception):
        pass

    assert isinstance(translate_sdk_error(FakeRateLimit("x")), AIRateLimitError)
    assert isinstance(translate_sdk_error(FakeTimeout("x")), AITimeoutError)
    assert isinstance(translate_sdk_error(FakeAuth("x")), AIProviderError)
    assert translate_sdk_error(FakeAuth("x")).code == "ai_authentication"
    assert isinstance(translate_sdk_error(FakeConnection("x")), AIProviderError)
    assert translate_sdk_error(FakeConnection("x")).code == "ai_network_error"
    assert isinstance(translate_sdk_error(RuntimeError("boom")), AIProviderError)


# --- retries -----------------------------------------------------------------


class _NullLogger:
    def warning(self, *args, **kwargs) -> None:
        pass


_NULL_LOGGER = _NullLogger()


async def _null_sleep(delay: float) -> None:
    pass


async def test_retries_succeed_after_transient_failures(monkeypatch) -> None:
    sleeps: list[float] = []

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", record_sleep)

    attempts = 0

    async def flaky_operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise AIRateLimitError("slow down")
        return "ok"

    policy = RetryPolicy(max_retries=3, base_delay_seconds=0.1, jitter=False)
    result = await with_retries(flaky_operation, policy, logger=_NULL_LOGGER)
    assert result == "ok"
    assert attempts == 3
    assert sleeps == [0.1, 0.2]  # exponential backoff


async def test_retries_give_up_after_max_retries(monkeypatch) -> None:
    monkeypatch.setattr(asyncio, "sleep", _null_sleep)
    attempts = 0

    async def always_fails() -> str:
        nonlocal attempts
        attempts += 1
        raise AIRateLimitError("slow down")

    policy = RetryPolicy(max_retries=2, base_delay_seconds=0.01, jitter=False)
    with pytest.raises(AIRateLimitError):
        await with_retries(always_fails, policy, logger=_NULL_LOGGER)
    assert attempts == 3  # initial + 2 retries


async def test_retries_do_not_retry_non_retriable_errors(monkeypatch) -> None:
    monkeypatch.setattr(asyncio, "sleep", _null_sleep)
    attempts = 0

    async def fails_hard() -> str:
        nonlocal attempts
        attempts += 1
        raise AIProviderError("permanent")

    policy = RetryPolicy(max_retries=5, base_delay_seconds=0.01, jitter=False)
    with pytest.raises(AIProviderError):
        await with_retries(fails_hard, policy, logger=None)
    assert attempts == 1


async def test_retries_enforce_timeout() -> None:
    async def never_returns() -> str:
        await asyncio.sleep(10)

    policy = RetryPolicy(max_retries=0, timeout_seconds=0.05)
    with pytest.raises(AITimeoutError):
        await with_retries(never_returns, policy, logger=None)


async def test_retries_are_bounded_by_max_delay(monkeypatch) -> None:
    sleeps: list[float] = []

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", record_sleep)
    attempts = 0

    async def flaky() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 5:
            raise AITimeoutError("slow")
        return "ok"

    policy = RetryPolicy(
        max_retries=5, base_delay_seconds=1.0, max_delay_seconds=2.0, jitter=False
    )
    assert await with_retries(flaky, policy, logger=_NULL_LOGGER) == "ok"
    assert sleeps == [1.0, 2.0, 2.0, 2.0]


# --- prompts -----------------------------------------------------------------


def test_prompt_loader_loads_and_renders() -> None:
    loader = PromptLoader()
    raw = loader.load("resume_tailor")
    assert "{{ company }}" in raw
    rendered = loader.render(
        "resume_tailor", company="Stripe", title="Engineer", location="Remote"
    )
    assert "Stripe" in rendered
    assert "{{" not in rendered


def test_prompt_loader_missing_prompt_raises() -> None:
    loader = PromptLoader()
    with pytest.raises(PromptNotFoundError):
        loader.load("does_not_exist")


def test_prompt_loader_supports_versioning() -> None:
    loader = PromptLoader()
    v1 = loader.load("resume_tailor")
    v2 = loader.load("resume_tailor@v2")
    assert v1 != v2
    assert "v2" in loader.versions("resume_tailor")
    with pytest.raises(PromptNotFoundError):
        loader.load("resume_tailor@v99")


def test_prompt_loader_caches_raw_text() -> None:
    loader = PromptLoader()
    first = loader.load("cover_letter")
    second = loader.load("cover_letter")
    assert first is second  # lru_cache returns the same string object


def test_prompt_loader_custom_directory(tmp_path: Path) -> None:
    (tmp_path / "custom.md").write_text("Hello {{ name }}", encoding="utf-8")
    loader = PromptLoader(prompts_dir=tmp_path)
    assert loader.load("custom") == "Hello {{ name }}"
    assert loader.render("custom", name="Ada") == "Hello Ada"


def test_prompt_manager_get_render_exists() -> None:
    assert manager.exists("cover_letter")
    assert "cover_letter" in manager.list_prompts()
    rendered = manager.render(
        "cover_letter", role="Engineer", company="Acme", candidate_name="Ada"
    )
    assert "Acme" in rendered
    assert "Ada" in rendered
    with pytest.raises(PromptNotFoundError):
        manager.get("missing_prompt")


def test_prompt_manager_undefined_variable_raises() -> None:
    with pytest.raises(PromptRenderError):
        manager.render(
            "cover_letter", role="Engineer"
        )  # company/candidate_name missing


def test_prompt_manager_custom_loader(tmp_path: Path) -> None:
    (tmp_path / "custom.md").write_text("Hi {{ who }}", encoding="utf-8")
    custom_manager = PromptManager(loader=PromptLoader(prompts_dir=tmp_path))
    assert custom_manager.render("custom", who="there") == "Hi there"


# --- usage tracker -----------------------------------------------------------


def test_usage_tracker_records_and_summarizes() -> None:
    tracker = UsageTracker()
    tracker.record(
        UsageRecord(
            provider="gemini",
            model="gemini-2.5-flash",
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.0002,
            latency_ms=120.0,
        )
    )
    tracker.record(
        UsageRecord(
            provider="gemini",
            model="gemini-2.5-flash",
            input_tokens=200,
            output_tokens=80,
            estimated_cost=0.0004,
            latency_ms=200.0,
        )
    )
    tracker.record(
        UsageRecord(
            provider="claude",
            model="claude-sonnet-4-5",
            input_tokens=10,
            output_tokens=5,
            estimated_cost=0.0001,
            latency_ms=80.0,
            success=False,
            error_type="AITimeoutError",
        )
    )
    summary = tracker.summary()
    assert summary.total_requests == 3
    assert summary.total_input_tokens == 310
    assert summary.total_output_tokens == 135
    assert summary.total_tokens == 445
    assert summary.failed_requests == 1
    assert summary.avg_latency_ms == pytest.approx(133.333, abs=0.01)
    assert set(summary.per_provider) == {"gemini", "claude"}
    assert summary.per_provider["gemini"].requests == 2
    assert summary.per_provider["claude"].failed_requests == 1


def test_usage_tracker_reset_and_defensive_copy() -> None:
    tracker = UsageTracker()
    tracker.record(UsageRecord(provider="gpt", model="gpt-5.5", input_tokens=1))
    records = tracker.records()
    records.clear()
    assert len(tracker) == 1
    tracker.reset()
    assert len(tracker) == 0
    assert tracker.summary().total_requests == 0


# --- factory -----------------------------------------------------------------


def test_factory_returns_registered_providers() -> None:
    factory = AIProviderFactory(settings=make_ai_settings())
    assert isinstance(factory.get_provider("gemini"), GeminiProvider)
    assert isinstance(factory.get_provider("claude"), ClaudeProvider)
    assert isinstance(factory.get_provider("gpt"), GPTProvider)
    assert factory.available() == ["claude", "gemini", "gpt"]


def test_factory_rejects_unknown_provider() -> None:
    factory = AIProviderFactory(settings=make_ai_settings())
    with pytest.raises(AIConfigurationError):
        factory.get_provider("ollama")


def test_factory_register_custom_provider() -> None:
    factory = AIProviderFactory(settings=make_ai_settings())

    class FakeProvider(GPTProvider):
        provider_name = "fake"

    factory.register("fake", FakeProvider)
    assert "fake" in factory.available()
    assert isinstance(factory.get_provider("fake"), FakeProvider)
    with pytest.raises(ValueError):
        factory.register("bad name", FakeProvider)


def test_factory_configured_excludes_missing_keys() -> None:
    settings = make_ai_settings(
        anthropic_api_key="", openai_api_key="", voyage_api_key=""
    )
    factory = AIProviderFactory(settings=settings)
    assert factory.configured() == ["gemini"]
    with pytest.raises(AIConfigurationError):
        factory.get_provider("claude")
