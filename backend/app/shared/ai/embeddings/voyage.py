"""Voyage embedding provider (voyageai SDK)."""

from __future__ import annotations

import time
from typing import Any

from app.shared.ai.exceptions import AIConfigurationError, translate_sdk_error
from app.shared.ai.interfaces import EmbeddingProvider
from app.shared.ai.models import EmbeddingResult
from app.shared.config import Settings, get_settings
from app.shared.logging import get_logger

#: model name -> USD per 1M tokens (input == output for embeddings).
PRICING: dict[str, float] = {
    "voyage-3-large": 0.06,
    "voyage-3": 0.02,
}
DEFAULT_PRICE_PER_MILLION = 0.02


class VoyageEmbeddingProvider(EmbeddingProvider):
    """Voyage AI implementation of the EmbeddingProvider interface."""

    provider_name = "voyage"
    default_model = "voyage-3-large"

    def __init__(
        self,
        settings: Settings | None = None,
        logger: Any | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._logger = logger or get_logger("app.shared.ai.embeddings.voyage")
        self._api_key_value = self._settings.ai.voyage_api_key.get_secret_value()
        if not self._api_key_value:
            raise AIConfigurationError(
                "voyage API key is not configured (see settings.ai.voyage_api_key)"
            )
        self._client = self._create_client()

    def _create_client(self) -> Any:
        from voyageai import AsyncClient

        return AsyncClient(api_key=self._api_key_value)

    def _model(self) -> str:
        return self._settings.ai.voyage_model

    def _build_result(
        self, embedding: list[float], *, tokens_used: int, started: float
    ) -> EmbeddingResult:
        return EmbeddingResult(
            embedding=embedding,
            model=self._model(),
            dimensions=len(embedding),
            tokens_used=tokens_used,
            estimated_cost=self._cost_for(tokens_used),
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            provider=self.provider_name,
        )

    def _cost_for(self, tokens: int) -> float:
        price = PRICING.get(self._model(), DEFAULT_PRICE_PER_MILLION)
        return round((tokens / 1_000_000) * price, 8)

    async def embed_text(self, text: str) -> EmbeddingResult:
        """Embed a single text."""
        started = time.perf_counter()
        try:
            response = await self._client.embed(texts=[text], model=self._model())
        except Exception as exc:
            raise translate_sdk_error(exc) from exc
        tokens = int(getattr(getattr(response, "usage", None), "total_tokens", 0) or 0)
        result = self._build_result(
            response.embeddings[0], tokens_used=tokens, started=started
        )
        self._log_embedding(result)
        return result

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """Embed many texts in a single provider request."""
        if not texts:
            return []
        started = time.perf_counter()
        try:
            response = await self._client.embed(texts=texts, model=self._model())
        except Exception as exc:
            raise translate_sdk_error(exc) from exc
        tokens = int(getattr(getattr(response, "usage", None), "total_tokens", 0) or 0)
        per_item = tokens // len(texts) if tokens else 0
        results = [
            self._build_result(embedding, tokens_used=per_item, started=started)
            for embedding in response.embeddings
        ]
        self._logger.info(
            "ai_embedding_request",
            provider=self.provider_name,
            model=self._model(),
            items=len(results),
            total_tokens=tokens,
            estimated_cost=sum(result.estimated_cost for result in results),
            execution_time_ms=round((time.perf_counter() - started) * 1000, 3),
            status="success",
        )
        return results

    def _log_embedding(self, result: EmbeddingResult) -> None:
        self._logger.info(
            "ai_embedding_request",
            provider=self.provider_name,
            model=result.model,
            items=1,
            total_tokens=result.tokens_used,
            estimated_cost=result.estimated_cost,
            execution_time_ms=result.latency_ms,
            status="success",
        )

    async def health(self) -> bool:
        try:
            await self._client.embed(texts=["ping"], model=self._model())
            return True
        except Exception:  # noqa: BLE001 — probes report any failure as unhealthy
            self._logger.warning("ai_health_check_failed", provider=self.provider_name)
            return False

    async def estimate_cost(self, tokens: int) -> float:
        """Estimate the USD cost of embedding ``tokens`` tokens."""
        return self._cost_for(tokens)


__all__ = ["VoyageEmbeddingProvider"]
