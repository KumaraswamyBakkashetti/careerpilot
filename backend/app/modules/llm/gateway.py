from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


ProviderErrorCategory = Literal[
    "MODEL_UNAVAILABLE",
    "MODEL_FORBIDDEN",
    "PROVIDER_UNAVAILABLE",
    "RATE_LIMITED",
    "INVALID_PROVIDER_CONFIGURATION",
    "INVALID_STRUCTURED_OUTPUT_CONFIGURATION",
    "MALFORMED_PROVIDER_RESPONSE",
]


class LLMProviderError(Exception):
    def __init__(
        self, category: ProviderErrorCategory, *, retry_after_seconds: float | None = None
    ) -> None:
        super().__init__(category)
        self.category = category
        self.retry_after_seconds = retry_after_seconds


class StructuredGenerationRequest(StrictModel):
    schema_name: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    schema_definition: dict[str, Any]
    system_prompt: str
    user_payload: str


class GenerationMetadata(StrictModel):
    provider: Literal["groq"] = "groq"
    model_id: str
    latency_ms: float = Field(ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class StructuredGenerationResult(StrictModel):
    value: dict[str, Any]
    metadata: GenerationMetadata


class ModelInfo(StrictModel):
    model_id: str
    active: bool
    context_window: int | None = Field(default=None, ge=1)
    owned_by: str | None = None


class LLMHealth(StrictModel):
    provider: Literal["groq"] = "groq"
    configured_model: str
    configured: bool
    live_available: bool
    structured_output_mode: Literal["strict_json_schema"] = "strict_json_schema"
    status: Literal["AVAILABLE", "UNAVAILABLE", "NOT_CONFIGURED"]
    error_category: ProviderErrorCategory | None = None


class LLMGateway(Protocol):
    @property
    def model_id(self) -> str: ...

    async def generate_structured(
        self, request: StructuredGenerationRequest
    ) -> StructuredGenerationResult: ...

    async def health_check(self) -> LLMHealth: ...

    async def model_info(self) -> list[ModelInfo]: ...

    async def close(self) -> None: ...
