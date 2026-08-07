"""Gemini provider wrapper (google-genai SDK)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, ClassVar

from app.shared.ai.models import AIResponse
from app.shared.ai.providers.base import BaseAIProvider


class GeminiProvider(BaseAIProvider):
    """Google Gemini implementation of the AIProvider interface."""

    provider_name = "gemini"
    default_model = "gemini-2.5-flash"
    PRICING: ClassVar[dict[str, tuple[float, float]]] = {
        "gemini-2.5-flash": (0.30, 2.50),
        "gemini-2.5-pro": (1.25, 10.00),
    }

    def _api_key(self) -> str:
        return self._settings.ai.gemini_api_key.get_secret_value()

    def _model(self) -> str:
        return self._settings.ai.gemini_model

    def _create_client(self) -> Any:
        from google import genai

        return genai.Client(api_key=self._api_key())

    def _config(
        self, *, system: str | None, temperature: float | None, max_tokens: int | None
    ) -> Any | None:
        if system is None and temperature is None and max_tokens is None:
            return None
        from google.genai import types

        return types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

    async def _call_generate(
        self,
        prompt: str,
        *,
        system: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> Any:
        response = await self._client.aio.models.generate_content(
            model=self._model(),
            contents=prompt,
            config=self._config(
                system=system, temperature=temperature, max_tokens=max_tokens
            ),
        )
        usage = response.usage_metadata
        finish_reason = (
            str(response.candidates[0].finish_reason) if response.candidates else None
        )
        return self._build_response(response, usage, finish_reason)

    def _build_response(
        self, response: Any, usage: Any, finish_reason: str | None
    ) -> AIResponse:
        return AIResponse(
            text=response.text or "",
            provider=self.provider_name,
            model=self._model(),
            input_tokens=getattr(usage, "prompt_token_count", None) or 0,
            output_tokens=getattr(usage, "candidates_token_count", None) or 0,
            finish_reason=finish_reason,
            raw_response={"candidates": len(response.candidates or [])},
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
            async for chunk in self._client.aio.models.generate_content_stream(
                model=self._model(),
                contents=prompt,
                config=self._config(
                    system=system, temperature=temperature, max_tokens=max_tokens
                ),
            ):
                if chunk.text:
                    yield chunk.text

        return _stream()

    async def health(self) -> bool:
        try:
            await self._client.aio.models.get(model=self._model())
            return True
        except Exception:  # noqa: BLE001 — probes report any failure as unhealthy
            self._logger.warning("ai_health_check_failed", provider=self.provider_name)
            return False

    async def count_tokens(self, text: str) -> int:
        result = await self._client.aio.models.count_tokens(
            model=self._model(), contents=text
        )
        return int(result.total_tokens or 0)


__all__ = ["GeminiProvider"]
