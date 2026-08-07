"""GPT provider wrapper (openai SDK)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, ClassVar

from app.shared.ai.providers.base import BaseAIProvider

_DEFAULT_MAX_TOKENS = 1024


class GPTProvider(BaseAIProvider):
    """OpenAI GPT implementation of the AIProvider interface."""

    provider_name = "gpt"
    default_model = "gpt-5.5"
    PRICING: ClassVar[dict[str, tuple[float, float]]] = {
        "gpt-4o": (2.50, 10.00),
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-5.5": (2.50, 10.00),
    }

    def _api_key(self) -> str:
        return self._settings.ai.openai_api_key.get_secret_value()

    def _model(self) -> str:
        return self._settings.ai.openai_model

    def _create_client(self) -> Any:
        from openai import AsyncOpenAI

        return AsyncOpenAI(api_key=self._api_key())

    def _messages(self, prompt: str, system: str | None) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _kwargs(
        self,
        prompt: str,
        *,
        system: str | None,
        temperature: float | None,
        max_tokens: int | None,
        **extra: Any,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self._model(),
            "messages": self._messages(prompt, system),
            **extra,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        return kwargs

    async def _call_generate(
        self,
        prompt: str,
        *,
        system: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> Any:
        completion = await self._client.chat.completions.create(
            **self._kwargs(
                prompt, system=system, temperature=temperature, max_tokens=max_tokens
            )
        )
        choice = completion.choices[0]
        text = choice.message.content or ""
        usage = completion.usage
        from app.shared.ai.models import AIResponse

        return AIResponse(
            text=text,
            provider=self.provider_name,
            model=self._model(),
            input_tokens=getattr(usage, "prompt_tokens", None) or 0,
            output_tokens=getattr(usage, "completion_tokens", None) or 0,
            finish_reason=choice.finish_reason,
            raw_response={"finish_reason": choice.finish_reason},
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
            stream = await self._client.chat.completions.create(
                **self._kwargs(
                    prompt,
                    system=system,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        return _stream()

    async def health(self) -> bool:
        try:
            await self._client.models.retrieve(model=self._model())
            return True
        except Exception:  # noqa: BLE001 — probes report any failure as unhealthy
            self._logger.warning("ai_health_check_failed", provider=self.provider_name)
            return False

    async def count_tokens(self, text: str) -> int:
        # Approximation (chars / 4); avoids a hard dependency on tiktoken.
        return max(1, len(text) // 4)


__all__ = ["GPTProvider"]
