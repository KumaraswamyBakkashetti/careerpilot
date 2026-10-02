from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

CanonicalId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{2,79}$")]
PrivateId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{2,79}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CompanyPreparationRequest(StrictModel):
    company_role_id: CanonicalId
    gap_run_id: PrivateId
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=120)


class CompanyFact(StrictModel):
    fact_type: Literal["COMPANY_ROLE", "GENERIC_ROLE", "ROLE_REQUIREMENT"]
    entity_id: CanonicalId
    label: str
    assertion_id: CanonicalId
    source_ids: list[CanonicalId]
    synthetic: bool


class PreparationItem(StrictModel):
    skill_id: CanonicalId
    skill_name: str
    importance: Literal["CORE", "EXPECTED", "OPTIONAL", "UNSPECIFIED"]
    student_status: Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "UNVERIFIED"]
    recommendation: str = Field(min_length=10, max_length=500)
    activities: list[str] = Field(min_length=1, max_length=4)
    evidence_ids: list[CanonicalId] = Field(min_length=1)
    resource_ids: list[CanonicalId]


class CompanyPreparation(StrictModel):
    preparation_id: PrivateId
    student_id: PrivateId
    company_id: CanonicalId
    company_name: str
    company_role_id: CanonicalId
    company_role_name: str
    generic_role_id: CanonicalId
    gap_run_id: PrivateId
    dataset_version: str
    synthetic: bool
    limitation: str
    prompt_version: Literal["company-prep-prompt-v1"] = "company-prep-prompt-v1"
    model_id: str
    retrieval_trace_ids: list[PrivateId]
    generation_run_id: PrivateId
    provider_latency_ms: float = Field(ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    facts: list[CompanyFact]
    items: list[PreparationItem]
    created_at: datetime


InterviewType = Literal["TECHNICAL_CONCEPTUAL", "ROLE_SPECIFIC"]
Difficulty = Literal["FOUNDATIONAL", "INTERMEDIATE", "ADVANCED"]


class InterviewStartRequest(StrictModel):
    company_role_id: CanonicalId
    interview_type: InterviewType
    difficulty: Difficulty = "INTERMEDIATE"
    question_count: int = Field(default=2, ge=1, le=5)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=120)


class RubricDimension(StrictModel):
    dimension: Literal["TECHNICAL_ACCURACY", "ROLE_RELEVANCE", "CLARITY", "GROUNDING"]
    criterion: str


class InterviewQuestion(StrictModel):
    question_id: PrivateId
    sequence: int = Field(ge=1)
    text: str = Field(min_length=10, max_length=800)
    topic_id: CanonicalId
    topic_name: str
    skill_ids: list[CanonicalId] = Field(min_length=1)
    evidence_ids: list[CanonicalId] = Field(min_length=1)
    difficulty: Difficulty
    rubric: list[RubricDimension] = Field(min_length=4, max_length=4)


class InterviewResponse(StrictModel):
    response_id: PrivateId
    question_id: PrivateId
    answer: str = Field(min_length=1, max_length=8000)
    submitted_at: datetime


Rating = Literal["STRONG", "ADEQUATE", "DEVELOPING", "INSUFFICIENT"]


class DimensionEvaluation(StrictModel):
    dimension: str
    rating: Rating
    feedback: str = Field(min_length=5, max_length=500)
    evidence_ids: list[CanonicalId]


class InterviewEvaluation(StrictModel):
    evaluation_id: PrivateId
    question_id: PrivateId
    response_id: PrivateId
    status: Literal["COMPLETED", "FAILED_RETRYABLE"]
    dimensions: list[DimensionEvaluation]
    strengths: list[str]
    improvements: list[str]
    practice_evidence_ids: list[PrivateId]
    prompt_version: Literal["interview-evaluation-prompt-v1"] = "interview-evaluation-prompt-v1"
    generation_run_id: PrivateId
    model_id: str
    provider_latency_ms: float = Field(ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    created_at: datetime


class InterviewSession(StrictModel):
    session_id: PrivateId
    student_id: PrivateId
    company_role_id: CanonicalId
    company_role_name: str
    interview_type: InterviewType
    difficulty: Difficulty
    status: Literal["ACTIVE", "COMPLETED"]
    prompt_version: Literal["interview-question-prompt-v1"] = "interview-question-prompt-v1"
    model_id: str
    generation_run_id: PrivateId
    provider_latency_ms: float = Field(ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    retrieval_trace_ids: list[PrivateId]
    questions: list[InterviewQuestion]
    responses: list[InterviewResponse] = Field(default_factory=list)
    evaluations: list[InterviewEvaluation] = Field(default_factory=list)
    created_at: datetime
    completed_at: datetime | None = None


class AnswerRequest(StrictModel):
    question_id: PrivateId
    answer: str = Field(min_length=1, max_length=8000)


class ReadinessRequest(StrictModel):
    gap_run_id: PrivateId
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=120)


class ReadinessComponent(StrictModel):
    component: Literal["ROLE_SKILL_COVERAGE", "EVIDENCE_COMPLETENESS", "INTERVIEW_PRACTICE"]
    score: int = Field(ge=0, le=100)
    weight: int = Field(ge=0, le=100)
    explanation: str
    evidence_ids: list[PrivateId | CanonicalId]


class ReadinessSnapshot(StrictModel):
    snapshot_id: PrivateId
    student_id: PrivateId
    gap_run_id: PrivateId
    score: int = Field(ge=0, le=100)
    category: Literal["FOUNDATION", "DEVELOPING", "PREPARING", "WELL_PREPARED"]
    rule_version: Literal["readiness-rules-v1"] = "readiness-rules-v1"
    version: int = Field(ge=1)
    components: list[ReadinessComponent] = Field(min_length=3, max_length=3)
    priority_skill_ids: list[CanonicalId]
    limitation: str
    created_at: datetime


class OrchestrationStep(StrictModel):
    module: str
    action: str
    status: Literal["COMPLETED", "FAILED"]


class OrchestrationRun(StrictModel):
    run_id: PrivateId
    student_id: PrivateId
    task_type: Literal["COMPANY_PREPARATION", "INTERVIEW", "READINESS"]
    workflow_version: Literal["specialist-orchestrator-v1"] = "specialist-orchestrator-v1"
    module_steps: list[OrchestrationStep]
    retrieval_trace_ids: list[PrivateId]
    generation_run_ids: list[PrivateId]
    result_id: PrivateId | None
    status: Literal["COMPLETED", "FAILED"]
    duration_ms: float = Field(ge=0)
    created_at: datetime


class SpecialistGenerationRun(StrictModel):
    run_id: PrivateId
    student_id: PrivateId
    task_type: Literal["COMPANY_PREPARATION", "INTERVIEW_QUESTION", "INTERVIEW_EVALUATION"]
    prompt_version: str
    model_id: str
    retrieval_trace_ids: list[PrivateId]
    result_id: PrivateId
    provider_latency_ms: float = Field(ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    created_at: datetime
