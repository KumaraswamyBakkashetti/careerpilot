import asyncio
import json
from time import perf_counter
from typing import Any

import httpx

from app.core.config import Settings
from app.modules.llm.gateway import (
    GenerationMetadata,
    LLMHealth,
    LLMProviderError,
    ModelInfo,
    ProviderErrorCategory,
    StructuredGenerationRequest,
    StructuredGenerationResult,
)


class GroqAdapter:
    """Groq HTTP details only; CareerPilot roadmap rules live outside this adapter."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client
        self._owns_client = client is None

    @property
    def model_id(self) -> str:
        return self.settings.groq_model

    @property
    def configured(self) -> bool:
        return bool(self.settings.groq_api_key.get_secret_value())

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.settings.groq_base_url,
                timeout=self.settings.groq_timeout_seconds,
                headers={
                    "Authorization": f"Bearer {self.settings.groq_api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    @staticmethod
    def _provider_error(response: httpx.Response) -> LLMProviderError:
        category: ProviderErrorCategory
        if response.status_code == 401:
            category = "INVALID_PROVIDER_CONFIGURATION"
        elif response.status_code == 403:
            category = "MODEL_FORBIDDEN"
        elif response.status_code == 404:
            category = "MODEL_UNAVAILABLE"
        elif response.status_code == 429:
            category = "RATE_LIMITED"
        elif response.status_code == 400:
            body = response.text.casefold()
            category = (
                "INVALID_STRUCTURED_OUTPUT_CONFIGURATION"
                if "schema" in body or "response_format" in body
                else "INVALID_PROVIDER_CONFIGURATION"
            )
        else:
            category = "PROVIDER_UNAVAILABLE"
        retry_after: float | None = None
        if response.headers.get("retry-after"):
            try:
                retry_after = float(response.headers["retry-after"])
            except ValueError:
                pass
        return LLMProviderError(category, retry_after_seconds=retry_after)

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        if not self.configured:
            raise LLMProviderError("INVALID_PROVIDER_CONFIGURATION")
        attempts = self.settings.groq_max_retries + 1
        for attempt in range(attempts):
            try:
                response = await self._http().post("/chat/completions", json=payload)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt + 1 >= attempts:
                    raise LLMProviderError("PROVIDER_UNAVAILABLE") from exc
                await asyncio.sleep(0.25 * (2**attempt))
                continue
            if response.status_code >= 500 and attempt + 1 < attempts:
                await asyncio.sleep(0.25 * (2**attempt))
                continue
            if response.is_error:
                raise self._provider_error(response)
            return response
        raise LLMProviderError("PROVIDER_UNAVAILABLE")

    async def generate_structured(
        self, request: StructuredGenerationRequest
    ) -> StructuredGenerationResult:
        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_payload},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "strict": True,
                    "schema": request.schema_definition,
                },
            },
            "reasoning_effort": self.settings.groq_reasoning_effort,
            "include_reasoning": False,
            "temperature": 0,
            "max_completion_tokens": 4096,
            # Intentionally no tools: no web search and no provider code execution.
        }
        started = perf_counter()
        response = await self._post(payload)
        latency_ms = round((perf_counter() - started) * 1000, 3)
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            value = json.loads(content)
            usage = data.get("usage") or {}
            details = usage.get("completion_tokens_details") or {}
            if not isinstance(value, dict):
                raise TypeError("structured result is not an object")
            return StructuredGenerationResult(
                value=value,
                metadata=GenerationMetadata(
                    model_id=str(data.get("model") or self.model_id),
                    latency_ms=latency_ms,
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                    reasoning_tokens=details.get("reasoning_tokens"),
                    total_tokens=usage.get("total_tokens"),
                ),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise LLMProviderError("MALFORMED_PROVIDER_RESPONSE") from exc

    async def model_info(self) -> list[ModelInfo]:
        if not self.configured:
            raise LLMProviderError("INVALID_PROVIDER_CONFIGURATION")
        try:
            response = await self._http().get("/models")
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise LLMProviderError("PROVIDER_UNAVAILABLE") from exc
        if response.is_error:
            raise self._provider_error(response)
        try:
            return [
                ModelInfo(
                    model_id=str(item["id"]),
                    active=bool(item.get("active", True)),
                    context_window=item.get("context_window"),
                    owned_by=item.get("owned_by"),
                )
                for item in response.json()["data"]
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise LLMProviderError("MALFORMED_PROVIDER_RESPONSE") from exc

    async def health_check(self) -> LLMHealth:
        if not self.configured:
            return LLMHealth(
                configured_model=self.model_id,
                configured=False,
                live_available=False,
                status="NOT_CONFIGURED",
                error_category="INVALID_PROVIDER_CONFIGURATION",
            )
        try:
            models = await self.model_info()
            available = any(item.model_id == self.model_id and item.active for item in models)
            return LLMHealth(
                configured_model=self.model_id,
                configured=True,
                live_available=available,
                status="AVAILABLE" if available else "UNAVAILABLE",
                error_category=None if available else "MODEL_UNAVAILABLE",
            )
        except LLMProviderError as exc:
            return LLMHealth(
                configured_model=self.model_id,
                configured=True,
                live_available=False,
                status="UNAVAILABLE",
                error_category=exc.category,
            )

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
        self._client = None
