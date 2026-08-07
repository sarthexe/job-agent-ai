"""Tests for AI providers and embeddings with fully mocked SDK clients.

No real API calls are made: every provider's ``_client`` is replaced
with a fake exposing the SDK surface the wrapper uses.
"""

import asyncio
from types import SimpleNamespace
from typing import Self

import pytest

from app.shared.ai.embeddings import VoyageEmbeddingProvider
from app.shared.ai.exceptions import (
    AIAuthenticationError,
    AIConfigurationError,
    AIProviderError,
    AIRateLimitError,
    AIResponseValidationError,
)
from app.shared.ai.providers import ClaudeProvider, GeminiProvider, GPTProvider
from app.shared.ai.usage import get_tracker
from tests.conftest import make_ai_settings

_ALL_PROVIDERS = [GeminiProvider, ClaudeProvider, GPTProvider]


class FakeRateLimitError(Exception):
    status_code = 429


class FakeAuthenticationError(Exception):
    status_code = 401


# --- fake SDK clients --------------------------------------------------------


def make_gemini_client(*, text: str = "hello from gemini", fail_times: int = 0):
    calls = {"count": 0}

    async def generate_content(model, contents, config=None):
        calls["count"] += 1
        if calls["count"] <= fail_times:
            raise FakeRateLimitError("quota exceeded")
        return SimpleNamespace(
            text=text,
            candidates=[SimpleNamespace(finish_reason="STOP")],
            usage_metadata=SimpleNamespace(
                prompt_token_count=10, candidates_token_count=5
            ),
        )

    async def stream_chunks(model, contents, config=None):
        for chunk in ("hello ", "from ", "gemini"):
            yield SimpleNamespace(text=chunk)

    async def get_model(model):
        return SimpleNamespace(name=model)

    async def count_tokens(model, contents):
        return SimpleNamespace(total_tokens=42)

    return SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(
                generate_content=generate_content,
                generate_content_stream=stream_chunks,
                get=get_model,
                count_tokens=count_tokens,
            )
        )
    )


class _FakeClaudeStream:
    """Mimics anthropic's MessageStream async context manager."""

    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    @property
    def text_stream(self):
        async def _gen():
            for chunk in self._chunks:
                yield chunk

        return _gen()


def make_claude_client(*, text: str = "hello from claude", fail_times: int = 0):
    calls = {"count": 0}

    async def messages_create(**kwargs):
        calls["count"] += 1
        if calls["count"] <= fail_times:
            raise FakeRateLimitError("quota exceeded")
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(input_tokens=20, output_tokens=7),
            stop_reason="end_turn",
        )

    def messages_stream(**kwargs):
        return _FakeClaudeStream(["hello ", "from ", "claude"])

    async def count_tokens(model, messages):
        return SimpleNamespace(input_tokens=64)

    return SimpleNamespace(
        messages=SimpleNamespace(
            create=messages_create,
            stream=messages_stream,
            count_tokens=count_tokens,
        )
    )


def make_gpt_client(*, text: str = "hello from gpt", fail_times: int = 0):
    calls = {"count": 0}

    async def completions_create(**kwargs):
        calls["count"] += 1
        if calls["count"] <= fail_times:
            raise FakeRateLimitError("quota exceeded")
        if kwargs.get("stream"):

            async def _chunks():
                for chunk_text in ("hello ", "from ", "gpt"):
                    yield SimpleNamespace(
                        choices=[
                            SimpleNamespace(delta=SimpleNamespace(content=chunk_text))
                        ]
                    )

            return _chunks()
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=text),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=30, completion_tokens=9),
        )

    async def retrieve(model):
        return SimpleNamespace(id=model)

    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=completions_create)),
        models=SimpleNamespace(retrieve=retrieve),
    )


@pytest.fixture
def tracker():
    tracker = get_tracker()
    tracker.reset()
    return tracker


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    async def _instant(delay: float) -> None:
        pass

    monkeypatch.setattr(asyncio, "sleep", _instant)


def _build(provider_cls, settings, client, tracker):
    provider = provider_cls(settings=settings, tracker=tracker)
    provider._client = client
    return provider


# --- generate ----------------------------------------------------------------


async def test_generate_returns_normalized_response(tracker) -> None:
    settings = make_ai_settings()
    cases = [
        (GeminiProvider, make_gemini_client(), "hello from gemini", 10, 5),
        (ClaudeProvider, make_claude_client(), "hello from claude", 20, 7),
        (GPTProvider, make_gpt_client(), "hello from gpt", 30, 9),
    ]
    for provider_cls, client, expected_text, in_tokens, out_tokens in cases:
        provider = _build(provider_cls, settings, client, tracker)
        response = await provider.generate("write a haiku")
        assert response.text == expected_text
        assert response.provider == provider_cls.provider_name
        assert response.model == provider._model()
        assert response.input_tokens == in_tokens
        assert response.output_tokens == out_tokens
        assert response.total_tokens == in_tokens + out_tokens
        assert response.estimated_cost > 0
        assert response.latency_ms >= 0
        assert response.request_id
        assert response.finish_reason is not None
        assert isinstance(response.raw_response, dict)


async def test_generate_accepts_system_and_parameters(tracker) -> None:
    settings = make_ai_settings()
    captured: dict = {}

    async def spy_generate_content(model, contents, config=None):
        captured["model"] = model
        captured["contents"] = contents
        captured["config"] = config
        return SimpleNamespace(
            text="ok",
            candidates=[SimpleNamespace(finish_reason="STOP")],
            usage_metadata=SimpleNamespace(
                prompt_token_count=1, candidates_token_count=1
            ),
        )

    client = make_gemini_client()
    client.aio.models.generate_content = spy_generate_content
    provider = _build(GeminiProvider, settings, client, tracker)
    await provider.generate("hi", system="be brief", temperature=0.2, max_tokens=50)
    assert captured["contents"] == "hi"
    assert captured["config"].system_instruction == "be brief"
    assert captured["config"].temperature == 0.2
    assert captured["config"].max_output_tokens == 50


# --- generate_json ------------------------------------------------------------


async def test_generate_json_parses_response(tracker) -> None:
    settings = make_ai_settings()
    client = make_gemini_client(text='{"role": "engineer", "years": 5}')
    provider = _build(GeminiProvider, settings, client, tracker)
    response = await provider.generate_json("extract the role")
    assert response.metadata["parsed"] == {"role": "engineer", "years": 5}


async def test_generate_json_rejects_invalid_json(tracker) -> None:
    settings = make_ai_settings()
    client = make_gemini_client(text="this is not json")
    provider = _build(GeminiProvider, settings, client, tracker)
    with pytest.raises(AIResponseValidationError):
        await provider.generate_json("extract the role")


# --- stream ------------------------------------------------------------------


async def test_stream_yields_chunks(tracker) -> None:
    settings = make_ai_settings()
    cases = [
        (GeminiProvider, make_gemini_client(), "hello from gemini"),
        (ClaudeProvider, make_claude_client(), "hello from claude"),
        (GPTProvider, make_gpt_client(), "hello from gpt"),
    ]
    for provider_cls, client, expected in cases:
        provider = _build(provider_cls, settings, client, tracker)
        chunks = [chunk async for chunk in provider.stream("tell me a story")]
        assert "".join(chunks) == expected


# --- health / tokens / cost --------------------------------------------------


async def test_health_true_when_client_available(tracker) -> None:
    settings = make_ai_settings()
    for provider_cls, client in [
        (GeminiProvider, make_gemini_client()),
        (ClaudeProvider, make_claude_client()),
        (GPTProvider, make_gpt_client()),
    ]:
        provider = _build(provider_cls, settings, client, tracker)
        assert await provider.health() is True


async def test_health_false_on_client_error(tracker) -> None:
    settings = make_ai_settings()

    async def boom(*args, **kwargs):
        raise FakeAuthenticationError("no access")

    gemini = _build(GeminiProvider, settings, make_gemini_client(), tracker)
    gemini._client.aio.models.get = boom
    assert await gemini.health() is False

    claude = _build(ClaudeProvider, settings, make_claude_client(), tracker)
    claude._client.messages.count_tokens = boom
    assert await claude.health() is False


async def test_count_tokens(tracker) -> None:
    settings = make_ai_settings()
    gemini = _build(GeminiProvider, settings, make_gemini_client(), tracker)
    assert await gemini.count_tokens("hello") == 42
    claude = _build(ClaudeProvider, settings, make_claude_client(), tracker)
    assert await claude.count_tokens("hello") == 64
    gpt = _build(GPTProvider, settings, make_gpt_client(), tracker)
    assert await gpt.count_tokens("a" * 16) == 4  # chars // 4 approximation


async def test_estimate_cost_uses_pricing_table(tracker) -> None:
    settings = make_ai_settings()
    gemini = _build(GeminiProvider, settings, make_gemini_client(), tracker)
    # 1M input @ $0.30 + 1M output @ $2.50 = $2.80 per 1M combined
    assert await gemini.estimate_cost(1_000_000, 1_000_000) == pytest.approx(2.80)


# --- retries + errors --------------------------------------------------------


async def test_generate_retries_then_succeeds(tracker) -> None:
    settings = make_ai_settings()
    client = make_gemini_client(fail_times=2)
    provider = _build(GeminiProvider, settings, client, tracker)
    response = await provider.generate("hi")
    assert response.text == "hello from gemini"


async def test_generate_raises_rate_limit_after_retries(tracker) -> None:
    settings = make_ai_settings()
    client = make_gemini_client(fail_times=99)
    provider = _build(GeminiProvider, settings, client, tracker)
    with pytest.raises(AIRateLimitError):
        await provider.generate("hi")


async def test_sdk_authentication_error_is_translated(tracker) -> None:
    settings = make_ai_settings()

    async def auth_boom(**kwargs):
        raise FakeAuthenticationError("bad key")

    client = make_gpt_client()
    client.chat.completions.create = auth_boom
    provider = _build(GPTProvider, settings, client, tracker)
    with pytest.raises(AIAuthenticationError):
        await provider.generate("hi")


async def test_unknown_sdk_error_is_wrapped_as_provider_error(tracker) -> None:
    settings = make_ai_settings()

    async def boom(**kwargs):
        raise RuntimeError("weird failure")

    client = make_claude_client()
    client.messages.create = boom
    provider = _build(ClaudeProvider, settings, client, tracker)
    with pytest.raises(AIProviderError):
        await provider.generate("hi")


# --- usage + logging ---------------------------------------------------------


async def test_usage_tracked_automatically(tracker) -> None:
    settings = make_ai_settings()
    provider = _build(GeminiProvider, settings, make_gemini_client(), tracker)
    await provider.generate("hi")
    summary = tracker.summary()
    assert summary.total_requests == 1
    assert summary.total_input_tokens == 10
    assert summary.total_output_tokens == 5
    assert summary.failed_requests == 0
    assert summary.per_provider["gemini"].requests == 1


async def test_failures_tracked_as_failed_requests(tracker) -> None:
    settings = make_ai_settings()

    async def boom(**kwargs):
        raise RuntimeError("down")

    client = make_gemini_client()
    client.aio.models.generate_content = boom
    provider = _build(GeminiProvider, settings, client, tracker)
    with pytest.raises(AIProviderError):
        await provider.generate("hi")
    summary = tracker.summary()
    assert summary.failed_requests == 1
    assert summary.total_requests == 1


async def test_generate_logs_structured_event(tracker) -> None:
    import structlog

    settings = make_ai_settings()
    provider = _build(GeminiProvider, settings, make_gemini_client(), tracker)
    with structlog.testing.capture_logs() as logs:
        await provider.generate("hi")
    ai_events = [entry for entry in logs if entry.get("event") == "ai_request"]
    assert ai_events
    event = ai_events[0]
    assert event["provider"] == "gemini"
    assert event["model"] == settings.ai.gemini_model
    assert event["status"] == "success"
    assert event["input_tokens"] == 10
    assert event["estimated_cost"] > 0
    assert "execution_time_ms" in event
    assert event["request_id"]


# --- embeddings --------------------------------------------------------------


def make_voyage_client(*, vectors: list[list[float]] | None = None, fail: bool = False):
    vectors = vectors or [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

    async def embed(texts, model):
        if fail:
            raise FakeRateLimitError("quota exceeded")
        return SimpleNamespace(
            embeddings=vectors[: len(texts)],
            usage=SimpleNamespace(total_tokens=len(texts) * 10),
        )

    return SimpleNamespace(embed=embed)


async def test_embed_text_returns_typed_result(tracker) -> None:
    settings = make_ai_settings()
    provider = VoyageEmbeddingProvider(settings=settings)
    provider._client = make_voyage_client(vectors=[[0.1, 0.2, 0.3]])
    result = await provider.embed_text("job description")
    assert result.embedding == [0.1, 0.2, 0.3]
    assert result.dimensions == 3
    assert result.provider == "voyage"
    assert result.tokens_used == 10
    assert result.estimated_cost > 0
    assert result.latency_ms >= 0
    assert result.model == settings.ai.voyage_model


async def test_embed_batch_returns_matching_results(tracker) -> None:
    settings = make_ai_settings()
    provider = VoyageEmbeddingProvider(settings=settings)
    provider._client = make_voyage_client()
    results = await provider.embed_batch(["first", "second"])
    assert len(results) == 2
    assert results[0].embedding == [0.1, 0.2, 0.3]
    assert results[1].embedding == [0.4, 0.5, 0.6]
    assert results[0].tokens_used == 10


async def test_embed_batch_empty_returns_empty_list(tracker) -> None:
    settings = make_ai_settings()
    provider = VoyageEmbeddingProvider(settings=settings)
    assert await provider.embed_batch([]) == []


async def test_embedding_health_and_cost(tracker) -> None:
    settings = make_ai_settings()
    healthy = VoyageEmbeddingProvider(settings=settings)
    healthy._client = make_voyage_client()
    assert await healthy.health() is True
    broken = VoyageEmbeddingProvider(settings=settings)
    broken._client = make_voyage_client(fail=True)
    assert await broken.health() is False
    assert await healthy.estimate_cost(1_000_000) == pytest.approx(0.06)


async def test_embedding_missing_key_raises(tracker) -> None:
    settings = make_ai_settings(voyage_api_key="")
    with pytest.raises(AIConfigurationError):
        VoyageEmbeddingProvider(settings=settings)


async def test_embedding_sdk_error_is_translated(tracker) -> None:
    settings = make_ai_settings()
    provider = VoyageEmbeddingProvider(settings=settings)
    provider._client = make_voyage_client(fail=True)
    with pytest.raises(AIRateLimitError):
        await provider.embed_text("hello")


# --- configuration -----------------------------------------------------------


def test_provider_missing_key_raises_configuration_error() -> None:
    settings = make_ai_settings(gemini_api_key="")
    with pytest.raises(AIConfigurationError):
        GeminiProvider(settings=settings)
