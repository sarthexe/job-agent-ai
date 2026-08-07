"""Claude provider wrapper (anthropic SDK)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, ClassVar

from app.shared.ai.providers.base import BaseAIProvider

_DEFAULT_MAX_TOKENS = 1024


class ClaudeProvider(BaseAIProvider):
    """Anthropic Claude implementation of the AIProvider interface."""

    provider_name = "claude"
    default_model = "claude-sonnet-4-5"
    PRICING: ClassVar[dict[str, tuple[float, float]]] = {
        "claude-sonnet-4-5": (3.00, 15.00),
        "claude-opus-4-1": (15.00, 75.00),
        "claude-haiku-4-5": (1.00, 5.00),
    }

    def _api_key(self) -> str:
        return self._settings.ai.anthropic_api_key.get_secret_value()

    def _model(self) -> str:
        return self._settings.ai.anthropic_model

    def _create_client(self) -> Any:
        from anthropic import AsyncAnthropic

        return AsyncAnthropic(api_key=self._api_key())

    def _messages(self, prompt: str) -> list[dict[str, str]]:
        return [{"role": "user", "content": prompt}]

    async def _call_generate(
        self,
        prompt: str,
        *,
        system: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self._model(),
            "max_tokens": max_tokens or _DEFAULT_MAX_TOKENS,
            "messages": self._messages(prompt),
        }
        if system:
            kwargs["system"] = system
        if temperature is not None:
            kwargs["temperature"] = temperature
        message = await self._client.messages.create(**kwargs)
        text = "".join(
            block.text
            for block in message.content
            if getattr(block, "type", "") == "text"
        )
        usage = message.usage
        from app.shared.ai.models import AIResponse

        return AIResponse(
            text=text,
            provider=self.provider_name,
            model=self._model(),
            input_tokens=getattr(usage, "input_tokens", None) or 0,
            output_tokens=getattr(usage, "output_tokens", None) or 0,
            finish_reason=message.stop_reason,
            raw_response={"stop_reason": message.stop_reason},
        )

    def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        async def _stream() -> AsyncIterator[str]:
            kwargs: dict[str, Any] = {
                "model": self._model(),
                "max_tokens": max_tokens or _DEFAULT_MAX_TOKENS,
                "messages": self._messages(prompt),
            }
            if system:
                kwargs["system"] = system
            if temperature is not None:
                kwargs["temperature"] = temperature
            async with self._client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text

        return _stream()

    async def health(self) -> bool:
        try:
            await self._client.messages.count_tokens(
                model=self._model(),
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception:  # noqa: BLE001 — probes report any failure as unhealthy
            self._logger.warning("ai_health_check_failed", provider=self.provider_name)
            return False

    async def count_tokens(self, text: str) -> int:
        result = await self._client.messages.count_tokens(
            model=self._model(), messages=self._messages(text)
        )
        return int(getattr(result, "input_tokens", 0) or 0)


__all__ = ["ClaudeProvider"]
