from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

CanonicalId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{2,79}$")]
RoadmapId = Annotated[str, Field(pattern=r"^roadmap_[a-f0-9]{32}$")]
GenerationId = Annotated[str, Field(pattern=r"^generation_[a-f0-9]{32}$")]
Priority = Literal["HIGH", "MEDIUM", "LOW"]
ReasonCode = Literal[
    "UNVERIFIED_CORE_REQUIREMENT",
    "PARTIALLY_SUPPORTED_CORE_REQUIREMENT",
    "UNVERIFIED_EXPECTED_REQUIREMENT",
    "PARTIALLY_SUPPORTED_EXPECTED_REQUIREMENT",
    "UNVERIFIED_OPTIONAL_REQUIREMENT",
    "PARTIALLY_SUPPORTED_OPTIONAL_REQUIREMENT",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RoadmapCreateRequest(StrictModel):
    gap_run_id: str = Field(pattern=r"^gap_[a-f0-9]{32}$")
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)


class RoadmapRegenerateRequest(StrictModel):
    idempotency_key: str = Field(min_length=8, max_length=128)


class RoadmapGenerationItem(StrictModel):
    skill_id: CanonicalId
    recommendation: str = Field(min_length=12, max_length=600)
    suggested_activities: list[str] = Field(min_length=1, max_length=6)


class RoadmapGeneration(StrictModel):
    items: list[RoadmapGenerationItem] = Field(min_length=1, max_length=100)


class RoadmapDraftItem(StrictModel):
    skill_id: CanonicalId
    priority: Priority
    reason_code: ReasonCode
    recommendation: str = Field(min_length=12, max_length=600)
    evidence_ids: list[str] = Field(min_length=1, max_length=30)
    resource_ids: list[CanonicalId] = Field(min_length=1, max_length=10)
    sequence: int = Field(ge=1, le=100)
    suggested_activities: list[str] = Field(min_length=1, max_length=6)


class RoadmapDraft(StrictModel):
    items: list[RoadmapDraftItem] = Field(min_length=1, max_length=100)


class RoadmapEvidence(StrictModel):
    evidence_id: str
    evidence_type: Literal["ROLE_REQUIREMENT", "STUDENT_STATUS", "RESOURCE"]
    skill_id: CanonicalId
    label: str
    source_id: str
    resource_id: CanonicalId | None = None
    resource_name: str | None = None
    text: str | None = None


class RoadmapItem(RoadmapDraftItem):
    item_id: str = Field(pattern=r"^roadmap_item_[a-f0-9]{32}$")
    skill_name: str
    status: Literal["NOT_STARTED", "IN_PROGRESS", "COMPLETED"] = "NOT_STARTED"


class Roadmap(StrictModel):
    roadmap_id: RoadmapId
    generation_run_id: GenerationId
    student_id: str = Field(pattern=r"^student_[a-f0-9]{32}$")
    target_role_id: CanonicalId
    gap_run_id: str = Field(pattern=r"^gap_[a-f0-9]{32}$")
    status: Literal["COMPLETED"] = "COMPLETED"
    version: int = Field(ge=1)
    generated_at: datetime
    prompt_version: Literal["roadmap-prompt-v1"] = "roadmap-prompt-v1"
    model_provider: Literal["groq"] = "groq"
    model_id: str
    retrieval_trace_ids: list[str]
    evidence_bundle_version: str
    coverage_status: Literal["SUFFICIENT", "PARTIAL"]
    omitted_skill_ids: list[CanonicalId]
    items: list[RoadmapItem]
    evidence: list[RoadmapEvidence]


GenerationStatus = Literal[
    "PENDING",
    "GENERATING",
    "VALIDATING",
    "COMPLETED",
    "FAILED_PROVIDER",
    "FAILED_RATE_LIMIT",
    "FAILED_SCHEMA",
    "FAILED_GROUNDING",
    "FAILED_EVIDENCE_REFERENCE",
    "FAILED_INSUFFICIENT_EVIDENCE",
]


class GenerationRun(StrictModel):
    run_id: GenerationId
    student_id: str = Field(pattern=r"^student_[a-f0-9]{32}$")
    task: Literal["GENERATE_ROADMAP"] = "GENERATE_ROADMAP"
    provider: Literal["groq"] = "groq"
    model_id: str
    prompt_version: Literal["roadmap-prompt-v1"] = "roadmap-prompt-v1"
    gap_run_id: str
    retrieval_trace_ids: list[str]
    input_evidence_ids: list[str]
    request_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_roadmap_id: RoadmapId | None = None
    latency_ms: float | None = Field(default=None, ge=0)
    retrieval_latency_ms: float | None = Field(default=None, ge=0)
    provider_latency_ms: float | None = Field(default=None, ge=0)
    validation_latency_ms: float | None = Field(default=None, ge=0)
    persistence_latency_ms: float | None = Field(default=None, ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    status: GenerationStatus
    error_category: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class RoadmapList(StrictModel):
    items: list[Roadmap]


class RoadmapEvidenceResponse(StrictModel):
    roadmap_id: RoadmapId
    retrieval_trace_ids: list[str]
    evidence: list[RoadmapEvidence]
