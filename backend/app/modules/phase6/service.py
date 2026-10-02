import asyncio
import hashlib
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.errors import ApplicationError
from app.modules.knowledge.models import EntityPage, RelationsPage
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.llm.gateway import (
    GenerationMetadata,
    LLMGateway,
    LLMProviderError,
    StructuredGenerationRequest,
)
from app.modules.phase6.models import (
    AnswerRequest,
    CompanyFact,
    CompanyPreparation,
    CompanyPreparationRequest,
    DimensionEvaluation,
    InterviewEvaluation,
    InterviewQuestion,
    InterviewResponse,
    InterviewSession,
    InterviewStartRequest,
    OrchestrationRun,
    OrchestrationStep,
    PreparationItem,
    ReadinessComponent,
    ReadinessRequest,
    ReadinessSnapshot,
    RubricDimension,
    SpecialistGenerationRun,
)
from app.modules.phase6.prompts import (
    COMPANY_SYSTEM,
    EVALUATION_SYSTEM,
    QUESTION_SYSTEM,
    company_schema,
    evaluation_schema,
    payload,
    question_schema,
)
from app.modules.phase6.repository import Phase6Repository
from app.modules.retrieval.models import EvidenceBundle, RetrievalRequest
from app.modules.retrieval.service import RetrievalService
from app.modules.student.models import GapAnalysisRun, SkillEvidence
from app.modules.student.repository import StudentRepository


def identifier(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def digest(*values: object) -> str:
    return hashlib.sha256("|".join(str(value) for value in values).encode()).hexdigest()


def contains_prohibited_claim(values: list[str], terms: set[str]) -> bool:
    text = " ".join(values).casefold()
    return any(term in text for term in terms)


class _CompanyItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skill_id: str
    recommendation: str = Field(min_length=10, max_length=500)
    activities: list[str] = Field(min_length=1, max_length=4)


class _CompanyOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[_CompanyItem]


class _QuestionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: str
    selection_note: str = Field(min_length=5, max_length=240)


class _QuestionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[_QuestionItem]


class _RatingOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: Literal["STRONG", "ADEQUATE", "DEVELOPING", "INSUFFICIENT"]
    feedback: str = Field(min_length=5, max_length=500)


class _EvaluationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    technical_accuracy: _RatingOutput
    role_relevance: _RatingOutput
    clarity: _RatingOutput
    grounding: _RatingOutput
    strengths: list[str]
    improvements: list[str]


class Phase6Service:
    QUESTION_TEMPLATES = {
        "topic_python_collections": (
            "Explain how you would count occurrences in a list using a Python dictionary, "
            "and compare its average time complexity with repeatedly searching a list."
        ),
        "topic_sql_joins": (
            "Explain the difference between an inner join and a left join, including how "
            "unmatched rows appear and one way you would verify the result."
        ),
        "topic_web_structure": (
            "Explain how semantic HTML structure and CSS responsibilities differ in a web page."
        ),
        "topic_assertions": (
            "Explain what a focused test assertion should verify and how failure output "
            "helps diagnosis."
        ),
        "topic_http_contracts": (
            "Explain how an HTTP API contract separates request validation, success, "
            "and error responses."
        ),
    }

    def __init__(
        self,
        students: StudentRepository,
        knowledge: KnowledgeRepository,
        retrieval: RetrievalService,
        repository: Phase6Repository,
        gateway: LLMGateway,
    ) -> None:
        self.students = students
        self.knowledge = knowledge
        self.retrieval = retrieval
        self.repository = repository
        self.gateway = gateway
        self._session_locks: dict[str, asyncio.Lock] = {}

    async def initialize(self) -> None:
        await self.repository.initialize()

    async def companies(self) -> EntityPage:
        return await self.knowledge.list_entities("Company", "", 50, 0)

    async def company_roles(self, company_id: str) -> RelationsPage:
        roles = await self.knowledge.related(company_id, "Company", "OFFERS_ROLE", False, 50, 0)
        if roles is None:
            raise ApplicationError("COMPANY_NOT_FOUND")
        return roles

    async def prepare(
        self, student_id: str, request_id: str, request: CompanyPreparationRequest
    ) -> CompanyPreparation:
        started = perf_counter()
        context = await self.knowledge.company_context(request.company_role_id)
        if context is None:
            raise ApplicationError("COMPANY_ROLE_NOT_FOUND")
        gap = await self.students.gap(student_id, request.gap_run_id)
        if gap is None:
            raise ApplicationError("GAP_ANALYSIS_NOT_FOUND")
        if gap.target_role_id != context.generic_role.entity.id:
            raise ApplicationError("COMPANY_ROLE_MISMATCH")
        requirements = await self.knowledge.related(
            request.company_role_id, "CompanyRole", "REQUIRES_SKILL", False, 100, 0
        )
        if requirements is None or not requirements.items:
            raise ApplicationError("COMPANY_EVIDENCE_INSUFFICIENT")
        gap_by_skill = {item.skill_id: item for item in gap.items}
        selected = [item for item in requirements.items if item.entity.id in gap_by_skill]
        if not selected:
            raise ApplicationError("COMPANY_EVIDENCE_INSUFFICIENT")
        bundles = {
            item.entity.id: await self.retrieval.gap_evidence(
                student_id, request_id, gap.run_id, item.entity.id, None
            )
            for item in selected
        }
        identity = digest(
            student_id,
            request.company_role_id,
            gap.evidence_snapshot_hash,
            self.gateway.model_id,
            request.idempotency_key or "default",
            *(str(sorted(bundle.versions.items())) for bundle in bundles.values()),
        )
        existing = await self.repository.preparation_by_identity(student_id, identity)
        if existing:
            return existing
        allowed = {
            skill_id: sorted(
                {
                    *(item.assertion_id for item in bundle.graph_evidence),
                    *(item.chunk_id for item in bundle.vector_evidence),
                }
            )
            for skill_id, bundle in bundles.items()
        }
        try:
            generated = await self.gateway.generate_structured(
                StructuredGenerationRequest(
                    schema_name="careerpilot_company_prep_v1",
                    schema_definition=company_schema(),
                    system_prompt=COMPANY_SYSTEM,
                    user_payload=payload(
                        "COMPANY_PREPARATION",
                        {
                            "synthetic": context.company.entity.synthetic,
                            "company": context.company.entity.model_dump(mode="json"),
                            "company_role": context.company_role.model_dump(mode="json"),
                            "generic_role": context.generic_role.entity.model_dump(mode="json"),
                            "skills": [
                                {
                                    "skill_id": item.entity.id,
                                    "skill_name": item.entity.name,
                                    "importance": item.evidence.assertion.importance,
                                    "student_status": gap_by_skill[item.entity.id].status,
                                    "allowed_evidence_ids": allowed[item.entity.id],
                                    "untrusted_resources": [
                                        {
                                            "chunk_id": value.chunk_id,
                                            "resource_id": value.resource_id,
                                            "text": value.text,
                                        }
                                        for value in bundles[item.entity.id].vector_evidence
                                    ],
                                }
                                for item in selected
                            ],
                        },
                    ),
                )
            )
            output = _CompanyOutput.model_validate(generated.value)
        except LLMProviderError as exc:
            if exc.category == "MALFORMED_PROVIDER_RESPONSE":
                raise ApplicationError("COMPANY_SCHEMA_INVALID") from exc
            raise ApplicationError(self._provider_error(exc)) from exc
        except ValidationError as exc:
            raise ApplicationError("COMPANY_SCHEMA_INVALID") from exc
        generated_by_skill = {item.skill_id: item for item in output.items}
        expected = {item.entity.id for item in selected}
        if len(output.items) != len(generated_by_skill) or set(generated_by_skill) != expected:
            raise ApplicationError("COMPANY_GROUNDING_INVALID")
        if contains_prohibited_claim(
            [text for item in output.items for text in [item.recommendation, *item.activities]],
            {
                "guarantee",
                "hiring process",
                "interview process",
                "always asks",
                "will hire",
                "recruiter",
                "you lack",
                "you are weak",
            },
        ):
            raise ApplicationError("COMPANY_GROUNDING_INVALID")
        facts = [
            CompanyFact(
                fact_type="COMPANY_ROLE",
                entity_id=context.company_role.id,
                label=f"{context.company.entity.name} offers {context.company_role.name}.",
                assertion_id=context.company.evidence.assertion.id,
                source_ids=[c.citation.source_id for c in context.company.evidence.provenance],
                synthetic=context.company.entity.synthetic,
            ),
            CompanyFact(
                fact_type="GENERIC_ROLE",
                entity_id=context.generic_role.entity.id,
                label=f"The company role is based on {context.generic_role.entity.name}.",
                assertion_id=context.generic_role.evidence.assertion.id,
                source_ids=[c.citation.source_id for c in context.generic_role.evidence.provenance],
                synthetic=context.generic_role.entity.synthetic,
            ),
        ]
        dataset_versions = {
            context.company.evidence.dataset_version,
            context.generic_role.evidence.dataset_version,
        }
        for relation in selected:
            dataset_versions.add(relation.evidence.dataset_version)
            facts.append(
                CompanyFact(
                    fact_type="ROLE_REQUIREMENT",
                    entity_id=relation.entity.id,
                    label=(
                        f"{relation.entity.name} is {relation.evidence.assertion.importance} "
                        "for this company role."
                    ),
                    assertion_id=relation.evidence.assertion.id,
                    source_ids=[c.citation.source_id for c in relation.evidence.provenance],
                    synthetic=any(c.source.synthetic for c in relation.evidence.provenance),
                )
            )
        if len(dataset_versions) != 1:
            raise ApplicationError("KNOWLEDGE_INCONSISTENT")
        run_id = identifier("generation")
        preparation = CompanyPreparation(
            preparation_id=identifier("preparation"),
            student_id=student_id,
            company_id=context.company.entity.id,
            company_name=context.company.entity.name,
            company_role_id=context.company_role.id,
            company_role_name=context.company_role.name,
            generic_role_id=context.generic_role.entity.id,
            gap_run_id=gap.run_id,
            dataset_version=dataset_versions.pop(),
            synthetic=context.company.entity.synthetic,
            limitation=(
                "Synthetic demonstration only; this is not evidence about a real employer."
                if context.company.entity.synthetic
                else "Coverage is limited to validated canonical company evidence."
            ),
            model_id=generated.metadata.model_id,
            retrieval_trace_ids=[bundle.trace_id for bundle in bundles.values()],
            generation_run_id=run_id,
            provider_latency_ms=generated.metadata.latency_ms,
            prompt_tokens=generated.metadata.prompt_tokens,
            completion_tokens=generated.metadata.completion_tokens,
            reasoning_tokens=generated.metadata.reasoning_tokens,
            total_tokens=generated.metadata.total_tokens,
            facts=facts,
            items=[
                PreparationItem(
                    skill_id=relation.entity.id,
                    skill_name=relation.entity.name,
                    importance=relation.evidence.assertion.importance or "UNSPECIFIED",
                    student_status=gap_by_skill[relation.entity.id].status,
                    recommendation=generated_by_skill[relation.entity.id].recommendation,
                    activities=generated_by_skill[relation.entity.id].activities,
                    evidence_ids=sorted(
                        {relation.evidence.assertion.id, *allowed[relation.entity.id]}
                    ),
                    resource_ids=sorted(
                        {x.resource_id for x in bundles[relation.entity.id].vector_evidence}
                    ),
                )
                for relation in selected
            ],
            created_at=datetime.now(UTC),
        )
        if not await self.repository.save_preparation(preparation, identity):
            concurrent = await self.repository.preparation_by_identity(student_id, identity)
            if concurrent:
                return concurrent
            raise ApplicationError("COMPANY_PREPARATION_IN_PROGRESS")
        await self._save_generation(
            student_id,
            run_id,
            "COMPANY_PREPARATION",
            preparation.prompt_version,
            preparation.preparation_id,
            preparation.retrieval_trace_ids,
            generated.metadata,
        )
        await self._trace(
            student_id,
            "COMPANY_PREPARATION",
            preparation.preparation_id,
            [run_id],
            preparation.retrieval_trace_ids,
            started,
            [
                "knowledge:company_context",
                "retrieval:hybrid",
                "llm:company_preparation",
                "persistence:mongodb",
            ],
        )
        return preparation

    async def start_interview(
        self, student_id: str, request_id: str, request: InterviewStartRequest
    ) -> InterviewSession:
        started = perf_counter()
        context = await self.knowledge.company_context(request.company_role_id)
        if context is None:
            raise ApplicationError("COMPANY_ROLE_NOT_FOUND")
        requirements = await self.knowledge.related(
            request.company_role_id, "CompanyRole", "REQUIRES_SKILL", False, 100, 0
        )
        topics = await self.knowledge.list_entities("InterviewTopic", "", 100, 0)
        if requirements is None or not requirements.items or not topics.items:
            raise ApplicationError("INTERVIEW_EVIDENCE_INSUFFICIENT")
        required_skills = {item.entity.id: item.entity for item in requirements.items}
        topic_rows: list[dict[str, Any]] = []
        for topic in topics.items:
            assessed = await self.knowledge.related(
                topic.id, "InterviewTopic", "ASSESSES_SKILL", False, 100, 0
            )
            if assessed is None:
                continue
            skill_ids = sorted({item.entity.id for item in assessed.items} & set(required_skills))
            if skill_ids:
                topic_rows.append(
                    {
                        "topic_id": topic.id,
                        "topic_name": topic.name,
                        "skill_ids": skill_ids,
                        "assertion_ids": [
                            item.evidence.assertion.id
                            for item in assessed.items
                            if item.entity.id in skill_ids
                        ],
                    }
                )
        if not topic_rows:
            raise ApplicationError("INTERVIEW_EVIDENCE_INSUFFICIENT")
        if request.question_count > len(topic_rows):
            raise ApplicationError("INTERVIEW_EVIDENCE_INSUFFICIENT")
        bundles: dict[str, EvidenceBundle] = {}
        for skill_id, skill in required_skills.items():
            bundles[skill_id] = await self.retrieval.execute(
                student_id,
                request_id,
                RetrievalRequest(task="SKILL_RESOURCES", skill_id=skill_id),
                trusted_skill_name=skill.name,
            )
        identity = digest(
            student_id,
            request.model_dump_json(),
            self.gateway.model_id,
            *(str(sorted(x.versions.items())) for x in bundles.values()),
        )
        existing = await self.repository.session_by_identity(student_id, identity)
        if existing:
            return existing
        allowed_evidence = sorted(
            {item for row in topic_rows for item in row["assertion_ids"]}
            | {item.chunk_id for bundle in bundles.values() for item in bundle.vector_evidence}
        )
        try:
            generated = await self.gateway.generate_structured(
                StructuredGenerationRequest(
                    schema_name="careerpilot_interview_questions_v1",
                    schema_definition=question_schema(),
                    system_prompt=QUESTION_SYSTEM,
                    user_payload=payload(
                        "INTERVIEW_QUESTIONS",
                        {
                            "interview_type": request.interview_type,
                            "difficulty": request.difficulty,
                            "question_count": request.question_count,
                            "synthetic_company": context.company.entity.synthetic,
                            "topics": topic_rows,
                            "allowed_evidence_ids": allowed_evidence,
                            "untrusted_resources": [
                                {"chunk_id": item.chunk_id, "skill_id": skill_id, "text": item.text}
                                for skill_id, bundle in bundles.items()
                                for item in bundle.vector_evidence
                            ],
                        },
                    ),
                )
            )
            output = _QuestionOutput.model_validate(generated.value)
        except LLMProviderError as exc:
            raise ApplicationError(self._provider_error(exc)) from exc
        except ValidationError as exc:
            raise ApplicationError("INTERVIEW_SCHEMA_INVALID") from exc
        topic_map = {row["topic_id"]: row for row in topic_rows}
        if len(output.items) != request.question_count or len(
            {item.topic_id for item in output.items}
        ) != len(output.items):
            raise ApplicationError("INTERVIEW_GROUNDING_INVALID")
        for item in output.items:
            if item.topic_id not in topic_map:
                raise ApplicationError("INTERVIEW_GROUNDING_INVALID")
        generation_id = identifier("generation")
        rubric = self.rubric()
        session = InterviewSession(
            session_id=identifier("interview"),
            student_id=student_id,
            company_role_id=request.company_role_id,
            company_role_name=context.company_role.name,
            interview_type=request.interview_type,
            difficulty=request.difficulty,
            status="ACTIVE",
            model_id=generated.metadata.model_id,
            generation_run_id=generation_id,
            provider_latency_ms=generated.metadata.latency_ms,
            prompt_tokens=generated.metadata.prompt_tokens,
            completion_tokens=generated.metadata.completion_tokens,
            reasoning_tokens=generated.metadata.reasoning_tokens,
            total_tokens=generated.metadata.total_tokens,
            retrieval_trace_ids=[x.trace_id for x in bundles.values()],
            questions=[
                InterviewQuestion(
                    question_id=identifier("question"),
                    sequence=index,
                    text=self.QUESTION_TEMPLATES[item.topic_id],
                    topic_id=item.topic_id,
                    topic_name=str(topic_map[item.topic_id]["topic_name"]),
                    skill_ids=list(topic_map[item.topic_id]["skill_ids"]),
                    evidence_ids=sorted(
                        {
                            *topic_map[item.topic_id]["assertion_ids"],
                            *(
                                evidence_id
                                for skill_id in topic_map[item.topic_id]["skill_ids"]
                                for evidence_id in (
                                    value.chunk_id for value in bundles[skill_id].vector_evidence
                                )
                            ),
                        }
                    ),
                    difficulty=request.difficulty,
                    rubric=rubric,
                )
                for index, item in enumerate(output.items, 1)
            ],
            created_at=datetime.now(UTC),
        )
        if not await self.repository.save_session(session, identity):
            concurrent = await self.repository.session_by_identity(student_id, identity)
            if concurrent:
                return concurrent
            raise ApplicationError("INTERVIEW_GENERATION_IN_PROGRESS")
        await self._save_generation(
            student_id,
            generation_id,
            "INTERVIEW_QUESTION",
            session.prompt_version,
            session.session_id,
            session.retrieval_trace_ids,
            generated.metadata,
        )
        await self._trace(
            student_id,
            "INTERVIEW",
            session.session_id,
            [generation_id],
            session.retrieval_trace_ids,
            started,
            [
                "knowledge:topics",
                "retrieval:hybrid",
                "llm:question_generation",
                "persistence:mongodb",
            ],
        )
        return session

    @staticmethod
    def rubric() -> list[RubricDimension]:
        return [
            RubricDimension(
                dimension="TECHNICAL_ACCURACY",
                criterion="Consistent with the supplied validated technical evidence.",
            ),
            RubricDimension(
                dimension="ROLE_RELEVANCE",
                criterion="Directly addresses the question and canonical skill.",
            ),
            RubricDimension(
                dimension="CLARITY",
                criterion="Communicates a coherent, understandable explanation.",
            ),
            RubricDimension(
                dimension="GROUNDING",
                criterion="Makes claims no broader than the supplied evidence supports.",
            ),
        ]

    async def answer(
        self, student_id: str, session_id: str, request: AnswerRequest
    ) -> InterviewSession:
        lock = self._session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            return await self._answer_locked(student_id, session_id, request)

    async def _answer_locked(
        self, student_id: str, session_id: str, request: AnswerRequest
    ) -> InterviewSession:
        started = perf_counter()
        session = await self.get_session(student_id, session_id)
        if session.status != "ACTIVE":
            raise ApplicationError("INVALID_INTERVIEW_STATE")
        question = next(
            (item for item in session.questions if item.question_id == request.question_id), None
        )
        if question is None:
            raise ApplicationError("INTERVIEW_QUESTION_NOT_FOUND")
        response = next(
            (item for item in session.responses if item.question_id == request.question_id), None
        )
        if response is not None and response.answer != request.answer:
            raise ApplicationError("DUPLICATE_INTERVIEW_RESPONSE")
        if response is None:
            response = InterviewResponse(
                response_id=identifier("response"),
                question_id=question.question_id,
                answer=request.answer,
                submitted_at=datetime.now(UTC),
            )
            session = session.model_copy(update={"responses": [*session.responses, response]})
            await self.repository.replace_session(session)  # Answer is durable before evaluation.
        prior = next(
            (
                item
                for item in session.evaluations
                if item.question_id == question.question_id and item.status == "COMPLETED"
            ),
            None,
        )
        if prior:
            return session
        evaluation_id = (
            f"evaluation_{digest(response.response_id, 'interview-evaluation-prompt-v1')[:32]}"
        )
        generation_id = f"generation_{digest(evaluation_id)[:32]}"
        try:
            generated = await self.gateway.generate_structured(
                StructuredGenerationRequest(
                    schema_name="careerpilot_interview_evaluation_v1",
                    schema_definition=evaluation_schema(),
                    system_prompt=EVALUATION_SYSTEM,
                    user_payload=payload(
                        "EVALUATE_ANSWER",
                        {
                            "question": question.text,
                            "canonical_skill_ids": question.skill_ids,
                            "fixed_rubric": [item.model_dump() for item in question.rubric],
                            "allowed_evidence_ids": question.evidence_ids,
                            "untrusted_student_answer": response.answer,
                        },
                    ),
                )
            )
            output = _EvaluationOutput.model_validate(generated.value)
            dimensions = [
                DimensionEvaluation(
                    dimension=name,
                    rating=value.rating,
                    feedback=value.feedback,
                    evidence_ids=question.evidence_ids,
                )
                for name, value in [
                    ("TECHNICAL_ACCURACY", output.technical_accuracy),
                    ("ROLE_RELEVANCE", output.role_relevance),
                    ("CLARITY", output.clarity),
                    ("GROUNDING", output.grounding),
                ]
            ]
            if contains_prohibited_claim(
                [
                    *output.strengths,
                    *output.improvements,
                    *(item.feedback for item in dimensions),
                ],
                {
                    "will be hired",
                    "hiring probability",
                    "you are an expert",
                    "you have mastered",
                    "you are incapable",
                },
            ):
                raise ApplicationError("INTERVIEW_EVALUATION_INVALID")
        except LLMProviderError as exc:
            failed = InterviewEvaluation(
                evaluation_id=evaluation_id,
                question_id=question.question_id,
                response_id=response.response_id,
                status="FAILED_RETRYABLE",
                dimensions=[],
                strengths=[],
                improvements=[],
                practice_evidence_ids=[],
                generation_run_id=generation_id,
                model_id=self.gateway.model_id,
                provider_latency_ms=0,
                created_at=datetime.now(UTC),
            )
            session = session.model_copy(
                update={
                    "evaluations": [
                        item
                        for item in session.evaluations
                        if item.question_id != question.question_id
                    ]
                    + [failed]
                }
            )
            await self.repository.replace_session(session)
            raise ApplicationError(self._provider_error(exc)) from exc
        except ValidationError as exc:
            raise ApplicationError("INTERVIEW_EVALUATION_INVALID") from exc
        creates_evidence = all(
            item.rating != "INSUFFICIENT"
            for item in dimensions
            if item.dimension in {"TECHNICAL_ACCURACY", "ROLE_RELEVANCE"}
        )
        practice: list[SkillEvidence] = []
        now = datetime.now(UTC)
        if creates_evidence:
            for skill_id in question.skill_ids:
                skill = await self.knowledge.entity(skill_id, "Skill")
                if skill:
                    practice.append(
                        SkillEvidence(
                            evidence_id=(f"evidence_{digest(evaluation_id, skill_id)[:32]}"),
                            student_id=student_id,
                            raw_text=f"Mock interview response for {skill.name}",
                            section="OTHER",
                            evidence_text=(
                                "Structured mock-interview evaluation produced practice "
                                "evidence; this is not confirmed mastery."
                            ),
                            skill_id=skill.id,
                            skill_name=skill.name,
                            normalization_status="EXACT",
                            source_type="INTERVIEW_PRACTICE",
                            extraction_method="INTERVIEW_EVALUATION_V1",
                            verification_status="EXTRACTED",
                            interview_session_id=session.session_id,
                            interview_question_id=question.question_id,
                            interview_evaluation_id=evaluation_id,
                            observed_at=response.submitted_at,
                            created_at=now,
                            updated_at=now,
                        )
                    )
            await self.students.save_evidence(practice)
        evaluation = InterviewEvaluation(
            evaluation_id=evaluation_id,
            question_id=question.question_id,
            response_id=response.response_id,
            status="COMPLETED",
            dimensions=dimensions,
            strengths=output.strengths,
            improvements=output.improvements,
            practice_evidence_ids=[item.evidence_id for item in practice],
            generation_run_id=generation_id,
            model_id=generated.metadata.model_id,
            provider_latency_ms=generated.metadata.latency_ms,
            prompt_tokens=generated.metadata.prompt_tokens,
            completion_tokens=generated.metadata.completion_tokens,
            reasoning_tokens=generated.metadata.reasoning_tokens,
            total_tokens=generated.metadata.total_tokens,
            created_at=now,
        )
        session = session.model_copy(
            update={
                "evaluations": [
                    item for item in session.evaluations if item.question_id != question.question_id
                ]
                + [evaluation]
            }
        )
        await self.repository.replace_session(session)
        await self._save_generation(
            student_id,
            generation_id,
            "INTERVIEW_EVALUATION",
            evaluation.prompt_version,
            evaluation.evaluation_id,
            session.retrieval_trace_ids,
            generated.metadata,
        )
        await self._trace(
            student_id,
            "INTERVIEW",
            evaluation.evaluation_id,
            [generation_id],
            session.retrieval_trace_ids,
            started,
            [
                "interview:immutable_response",
                "llm:rubric_evaluation",
                "student:practice_evidence",
            ],
        )
        return session

    async def complete_interview(self, student_id: str, session_id: str) -> InterviewSession:
        session = await self.get_session(student_id, session_id)
        answered = {item.question_id for item in session.responses}
        evaluated = {item.question_id for item in session.evaluations if item.status == "COMPLETED"}
        expected = {item.question_id for item in session.questions}
        if answered != expected or evaluated != expected:
            raise ApplicationError("INVALID_INTERVIEW_STATE")
        if session.status == "COMPLETED":
            return session
        session = session.model_copy(
            update={"status": "COMPLETED", "completed_at": datetime.now(UTC)}
        )
        await self.repository.replace_session(session)
        return session

    async def get_session(self, student_id: str, session_id: str) -> InterviewSession:
        value = await self.repository.session(student_id, session_id)
        if value is None:
            raise ApplicationError("INTERVIEW_NOT_FOUND")
        return value

    async def readiness(self, student_id: str, request: ReadinessRequest) -> ReadinessSnapshot:
        started = perf_counter()
        gap = await self.students.gap(student_id, request.gap_run_id)
        if gap is None:
            raise ApplicationError("GAP_ANALYSIS_NOT_FOUND")
        evidence = await self.students.evidence(student_id)
        sessions = await self.repository.sessions(student_id)
        identity = digest(
            student_id,
            gap.evidence_snapshot_hash,
            request.idempotency_key or "default",
            *(
                evaluation.evaluation_id
                for session in sessions
                for evaluation in session.evaluations
                if evaluation.status == "COMPLETED"
            ),
        )
        existing = await self.repository.readiness_by_identity(student_id, identity)
        if existing:
            return existing
        snapshot = self.calculate_readiness(
            student_id,
            gap,
            evidence,
            sessions,
            await self.repository.next_readiness_version(student_id),
        )
        if not await self.repository.save_readiness(snapshot, identity):
            concurrent = await self.repository.readiness_by_identity(student_id, identity)
            if concurrent:
                return concurrent
            raise ApplicationError("READINESS_CALCULATION_IN_PROGRESS")
        await self._trace(
            student_id,
            "READINESS",
            snapshot.snapshot_id,
            [],
            [],
            started,
            [
                "student:gap_snapshot",
                "student:evidence",
                "interview:evaluations",
                "rules:readiness-v1",
                "persistence:mongodb",
            ],
        )
        return snapshot

    @staticmethod
    def calculate_readiness(
        student_id: str,
        gap: GapAnalysisRun,
        evidence: list[SkillEvidence],
        sessions: list[InterviewSession],
        version: int,
    ) -> ReadinessSnapshot:
        importance = {"CORE": 3, "EXPECTED": 2, "OPTIONAL": 1, "UNSPECIFIED": 1}
        status_score = {"SUPPORTED": 100, "PARTIALLY_SUPPORTED": 50, "UNVERIFIED": 0}
        total_weight = sum(importance[item.importance] for item in gap.items) or 1
        role_score = round(
            sum(status_score[item.status] * importance[item.importance] for item in gap.items)
            / total_weight
        )
        eligible = [
            item
            for item in evidence
            if item.verification_status != "REJECTED"
            and item.skill_id in {gap_item.skill_id for gap_item in gap.items}
        ]
        represented = {item.skill_id for item in eligible}
        evidence_score = round(100 * len(represented) / len(gap.items)) if gap.items else 0
        evaluations = [
            evaluation
            for session in sessions
            for evaluation in session.evaluations
            if evaluation.status == "COMPLETED"
        ]
        practiced = {
            skill_id
            for session in sessions
            for question in session.questions
            for skill_id in question.skill_ids
            if any(e.question_id == question.question_id for e in evaluations)
        }
        interview_score = (
            min(
                100,
                round(
                    100 * len(practiced & {item.skill_id for item in gap.items}) / len(gap.items)
                ),
            )
            if gap.items
            else 0
        )
        score = round(role_score * 0.5 + evidence_score * 0.25 + interview_score * 0.25)
        category: Literal["FOUNDATION", "DEVELOPING", "PREPARING", "WELL_PREPARED"] = (
            "FOUNDATION"
            if score < 25
            else "DEVELOPING"
            if score < 50
            else "PREPARING"
            if score < 75
            else "WELL_PREPARED"
        )
        return ReadinessSnapshot(
            snapshot_id=identifier("readiness"),
            student_id=student_id,
            gap_run_id=gap.run_id,
            score=score,
            category=category,
            version=version,
            components=[
                ReadinessComponent(
                    component="ROLE_SKILL_COVERAGE",
                    score=role_score,
                    weight=50,
                    explanation=(
                        "Importance-weighted gap classifications: supported=100, "
                        "partial=50, unverified=0."
                    ),
                    evidence_ids=[gap.run_id],
                ),
                ReadinessComponent(
                    component="EVIDENCE_COMPLETENESS",
                    score=evidence_score,
                    weight=25,
                    explanation=(
                        "Share of required skills represented by non-rejected resume or "
                        "practice evidence."
                    ),
                    evidence_ids=[item.evidence_id for item in eligible],
                ),
                ReadinessComponent(
                    component="INTERVIEW_PRACTICE",
                    score=interview_score,
                    weight=25,
                    explanation=(
                        "Share of required skills covered by completed structured "
                        "mock-interview evaluations."
                    ),
                    evidence_ids=[item.evaluation_id for item in evaluations],
                ),
            ],
            priority_skill_ids=[item.skill_id for item in gap.items if item.status != "SUPPORTED"],
            limitation=(
                "Preparation readiness is an evidence-backed planning indicator, not a "
                "hiring, placement, or employment probability."
            ),
            created_at=datetime.now(UTC),
        )

    async def get_preparation(self, student_id: str, identifier: str) -> CompanyPreparation:
        value = await self.repository.preparation(student_id, identifier)
        if value is None:
            raise ApplicationError("COMPANY_PREPARATION_NOT_FOUND")
        return value

    async def get_readiness(self, student_id: str, identifier: str) -> ReadinessSnapshot:
        value = await self.repository.readiness(student_id, identifier)
        if value is None:
            raise ApplicationError("READINESS_NOT_FOUND")
        return value

    async def latest_readiness(self, student_id: str) -> ReadinessSnapshot:
        value = await self.repository.latest_readiness(student_id)
        if value is None:
            raise ApplicationError("READINESS_NOT_FOUND")
        return value

    async def orchestration(self, student_id: str, identifier: str) -> OrchestrationRun:
        value = await self.repository.orchestration(student_id, identifier)
        if value is None:
            raise ApplicationError("ORCHESTRATION_NOT_FOUND")
        return value

    async def _trace(
        self,
        student_id: str,
        task: Literal["COMPANY_PREPARATION", "INTERVIEW", "READINESS"],
        result_id: str,
        generation_ids: list[str],
        retrieval_ids: list[str],
        started: float,
        steps: list[str],
    ) -> None:
        await self.repository.save_orchestration(
            OrchestrationRun(
                run_id=identifier("orchestration"),
                student_id=student_id,
                task_type=task,
                module_steps=[
                    OrchestrationStep(
                        module=value.split(":", 1)[0],
                        action=value.split(":", 1)[1],
                        status="COMPLETED",
                    )
                    for value in steps
                ],
                retrieval_trace_ids=retrieval_ids,
                generation_run_ids=generation_ids,
                result_id=result_id,
                status="COMPLETED",
                duration_ms=round((perf_counter() - started) * 1000, 3),
                created_at=datetime.now(UTC),
            )
        )

    async def _save_generation(
        self,
        student_id: str,
        run_id: str,
        task_type: Literal["COMPANY_PREPARATION", "INTERVIEW_QUESTION", "INTERVIEW_EVALUATION"],
        prompt_version: str,
        result_id: str,
        retrieval_trace_ids: list[str],
        metadata: GenerationMetadata,
    ) -> None:
        await self.repository.save_generation(
            SpecialistGenerationRun(
                run_id=run_id,
                student_id=student_id,
                task_type=task_type,
                prompt_version=prompt_version,
                model_id=metadata.model_id,
                retrieval_trace_ids=retrieval_trace_ids,
                result_id=result_id,
                provider_latency_ms=metadata.latency_ms,
                prompt_tokens=metadata.prompt_tokens,
                completion_tokens=metadata.completion_tokens,
                reasoning_tokens=metadata.reasoning_tokens,
                total_tokens=metadata.total_tokens,
                created_at=datetime.now(UTC),
            )
        )

    @staticmethod
    def _provider_error(exc: LLMProviderError) -> Any:
        return {
            "MODEL_UNAVAILABLE": "MODEL_UNAVAILABLE",
            "MODEL_FORBIDDEN": "MODEL_FORBIDDEN",
            "PROVIDER_UNAVAILABLE": "PROVIDER_UNAVAILABLE",
            "RATE_LIMITED": "RATE_LIMITED",
            "INVALID_PROVIDER_CONFIGURATION": "INVALID_PROVIDER_CONFIGURATION",
            "INVALID_STRUCTURED_OUTPUT_CONFIGURATION": "INVALID_STRUCTURED_OUTPUT_CONFIGURATION",
            "MALFORMED_PROVIDER_RESPONSE": "INTERVIEW_SCHEMA_INVALID",
        }[exc.category]
