import hashlib
import json
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from pydantic import ValidationError

from app.core.errors import ApplicationError, ErrorCode
from app.modules.llm.gateway import LLMGateway, LLMProviderError, StructuredGenerationRequest
from app.modules.retrieval.models import EvidenceBundle
from app.modules.retrieval.service import RetrievalService
from app.modules.roadmap.models import (
    GenerationRun,
    Roadmap,
    RoadmapEvidence,
    RoadmapEvidenceResponse,
    RoadmapGeneration,
    RoadmapItem,
    RoadmapList,
)
from app.modules.roadmap.prompt import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    Envelope,
    build_envelopes,
    build_prompt,
    enrich_generation,
    roadmap_schema,
)
from app.modules.roadmap.repository import RoadmapRepository
from app.modules.roadmap.validator import (
    EvidenceReferenceViolation,
    GroundingViolation,
    validate_evidence_references,
    validate_grounding,
)
from app.modules.student.repository import StudentRepository

PROVIDER_ERROR_MAP: dict[str, ErrorCode] = {
    "MODEL_UNAVAILABLE": "MODEL_UNAVAILABLE",
    "MODEL_FORBIDDEN": "MODEL_FORBIDDEN",
    "PROVIDER_UNAVAILABLE": "PROVIDER_UNAVAILABLE",
    "RATE_LIMITED": "RATE_LIMITED",
    "INVALID_PROVIDER_CONFIGURATION": "INVALID_PROVIDER_CONFIGURATION",
    "INVALID_STRUCTURED_OUTPUT_CONFIGURATION": "INVALID_STRUCTURED_OUTPUT_CONFIGURATION",
    "MALFORMED_PROVIDER_RESPONSE": "ROADMAP_SCHEMA_INVALID",
}


class RoadmapService:
    def __init__(
        self,
        students: StudentRepository,
        retrieval: RetrievalService,
        repository: RoadmapRepository,
        gateway: LLMGateway,
    ) -> None:
        self.students = students
        self.retrieval = retrieval
        self.repository = repository
        self.gateway = gateway

    async def initialize(self) -> None:
        await self.repository.initialize()

    @staticmethod
    def _identity(
        student_id: str,
        gap_snapshot: str,
        model_id: str,
        bundles: dict[str, EvidenceBundle],
        idempotency_key: str | None,
    ) -> str:
        versions = sorted(
            json.dumps(value.versions, sort_keys=True, separators=(",", ":"))
            for value in bundles.values()
        )
        value = "|".join(
            [
                student_id,
                gap_snapshot,
                PROMPT_VERSION,
                model_id,
                *versions,
                idempotency_key or "default",
            ]
        )
        return hashlib.sha256(value.encode()).hexdigest()

    @staticmethod
    def _bundle_version(envelopes: list[Envelope]) -> str:
        value = [
            {
                "skill": item.gap.skill_id,
                "trace": item.bundle.trace_id,
                "versions": item.bundle.versions,
                "evidence": item.evidence_ids,
            }
            for item in envelopes
        ]
        return (
            "evidence-bundle-"
            + hashlib.sha256(
                json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()[:24]
        )

    @staticmethod
    def _evidence(envelopes: list[Envelope], gap_run_id: str) -> list[RoadmapEvidence]:
        values: list[RoadmapEvidence] = []
        for envelope in envelopes:
            graph_source = next(
                (
                    item.source_ids[0]
                    for item in envelope.bundle.graph_evidence
                    if item.assertion_id == envelope.gap.graph_assertion_id and item.source_ids
                ),
                envelope.bundle.versions.get("knowledge", "knowledge_snapshot"),
            )
            values.append(
                RoadmapEvidence(
                    evidence_id=envelope.gap.graph_assertion_id,
                    evidence_type="ROLE_REQUIREMENT",
                    skill_id=envelope.gap.skill_id,
                    label=(
                        f"{envelope.gap.skill_name} is {envelope.gap.importance} "
                        "for the target role."
                    ),
                    source_id=graph_source,
                )
            )
            values.append(
                RoadmapEvidence(
                    evidence_id=envelope.status_evidence_id,
                    evidence_type="STUDENT_STATUS",
                    skill_id=envelope.gap.skill_id,
                    label=(
                        "CareerPilot has no confirmed direct evidence for this skill."
                        if envelope.gap.status == "UNVERIFIED"
                        else "CareerPilot has direct evidence that is not yet fully confirmed."
                    ),
                    source_id=gap_run_id,
                )
            )
            for item in envelope.bundle.vector_evidence:
                values.append(
                    RoadmapEvidence(
                        evidence_id=item.chunk_id,
                        evidence_type="RESOURCE",
                        skill_id=envelope.gap.skill_id,
                        label="Validated learning resource passage.",
                        source_id=item.source_id,
                        resource_id=item.resource_id,
                        resource_name=str(item.metadata.get("resource_name", item.resource_id)),
                        text=item.text,
                    )
                )
        return values

    async def generate(
        self,
        student_id: str,
        request_id: str,
        gap_run_id: str,
        idempotency_key: str | None = None,
    ) -> Roadmap:
        started = perf_counter()
        gap_run = await self.students.gap(student_id, gap_run_id)
        if gap_run is None:
            raise ApplicationError("GAP_ANALYSIS_NOT_FOUND")
        actionable = [item for item in gap_run.items if item.status != "SUPPORTED"]
        if not actionable:
            raise ApplicationError("ROADMAP_EVIDENCE_INSUFFICIENT")
        retrieval_started = perf_counter()
        bundles = {
            item.skill_id: await self.retrieval.gap_evidence(
                student_id, request_id, gap_run_id, item.skill_id, None
            )
            for item in actionable
        }
        retrieval_ms = round((perf_counter() - retrieval_started) * 1000, 3)
        identity = self._identity(
            student_id,
            gap_run.evidence_snapshot_hash,
            self.gateway.model_id,
            bundles,
            idempotency_key,
        )
        existing = await self.repository.by_identity(student_id, identity)
        if existing is not None:
            return existing
        all_envelopes = build_envelopes(gap_run, bundles)
        # Never send an insufficient gap to the model. Generate the grounded subset and
        # persist omitted IDs so partial coverage remains explicit to the student.
        envelopes = [
            item
            for item in all_envelopes
            if item.bundle.sufficiency.status != "INSUFFICIENT" and item.resource_ids
        ]
        omitted_skill_ids = [item.gap.skill_id for item in all_envelopes if item not in envelopes]
        if not envelopes:
            await self._failed_run(
                student_id,
                gap_run_id,
                identity,
                all_envelopes,
                retrieval_ms,
                "FAILED_INSUFFICIENT_EVIDENCE",
                "ROADMAP_EVIDENCE_INSUFFICIENT",
            )
            raise ApplicationError("ROADMAP_EVIDENCE_INSUFFICIENT")
        run = GenerationRun(
            run_id=f"generation_{uuid4().hex}",
            student_id=student_id,
            model_id=self.gateway.model_id,
            gap_run_id=gap_run_id,
            retrieval_trace_ids=[item.bundle.trace_id for item in envelopes],
            input_evidence_ids=sorted({value for item in envelopes for value in item.evidence_ids}),
            request_identity=identity,
            retrieval_latency_ms=retrieval_ms,
            status="GENERATING",
            created_at=datetime.now(UTC),
        )
        claimed = await self.repository.save_run(run)
        if not claimed:
            concurrent = await self.repository.by_identity(student_id, identity)
            if concurrent is not None:
                return concurrent
            raise ApplicationError("ROADMAP_GENERATION_IN_PROGRESS")
        try:
            result = await self.gateway.generate_structured(
                StructuredGenerationRequest(
                    schema_name="careerpilot_roadmap_v1",
                    schema_definition=roadmap_schema(),
                    system_prompt=SYSTEM_PROMPT,
                    user_payload=build_prompt(gap_run.target_role_id, envelopes),
                )
            )
        except LLMProviderError as exc:
            failed_status = (
                "FAILED_RATE_LIMIT" if exc.category == "RATE_LIMITED" else "FAILED_PROVIDER"
            )
            await self.repository.replace_run(
                run.model_copy(
                    update={
                        "status": failed_status,
                        "error_category": exc.category,
                        "completed_at": datetime.now(UTC),
                        "latency_ms": round((perf_counter() - started) * 1000, 3),
                    }
                )
            )
            raise ApplicationError(PROVIDER_ERROR_MAP[exc.category]) from exc
        validating = run.model_copy(update={"status": "VALIDATING"})
        await self.repository.replace_run(validating)
        validation_started = perf_counter()
        try:
            generation = RoadmapGeneration.model_validate(result.value)
        except ValidationError as exc:
            await self._validation_failure(validating, started, "FAILED_SCHEMA", "SCHEMA_INVALID")
            raise ApplicationError("ROADMAP_SCHEMA_INVALID") from exc
        try:
            draft = enrich_generation(generation, envelopes)
        except ValueError as exc:
            await self._validation_failure(
                validating, started, "FAILED_GROUNDING", "GROUNDING_INVALID"
            )
            raise ApplicationError("ROADMAP_GROUNDING_INVALID") from exc
        try:
            validate_grounding(draft, envelopes)
        except GroundingViolation as exc:
            await self._validation_failure(
                validating, started, "FAILED_GROUNDING", "GROUNDING_INVALID"
            )
            raise ApplicationError("ROADMAP_GROUNDING_INVALID") from exc
        try:
            validate_evidence_references(draft, envelopes)
        except EvidenceReferenceViolation as exc:
            await self._validation_failure(
                validating,
                started,
                "FAILED_EVIDENCE_REFERENCE",
                "EVIDENCE_REFERENCE_INVALID",
            )
            raise ApplicationError("ROADMAP_EVIDENCE_REFERENCE_INVALID") from exc
        validation_ms = round((perf_counter() - validation_started) * 1000, 3)
        names = {item.gap.skill_id: item.gap.skill_name for item in envelopes}
        roadmap_id = f"roadmap_{uuid4().hex}"
        generated_at = datetime.now(UTC)
        roadmap = Roadmap(
            roadmap_id=roadmap_id,
            generation_run_id=run.run_id,
            student_id=student_id,
            target_role_id=gap_run.target_role_id,
            gap_run_id=gap_run_id,
            version=await self.repository.next_version(student_id),
            generated_at=generated_at,
            model_id=result.metadata.model_id,
            retrieval_trace_ids=run.retrieval_trace_ids,
            evidence_bundle_version=self._bundle_version(envelopes),
            coverage_status="PARTIAL" if omitted_skill_ids else "SUFFICIENT",
            omitted_skill_ids=omitted_skill_ids,
            items=[
                RoadmapItem(
                    item_id=f"roadmap_item_{uuid4().hex}",
                    skill_name=names[item.skill_id],
                    **item.model_dump(),
                )
                for item in sorted(draft.items, key=lambda value: value.sequence)
            ],
            evidence=self._evidence(envelopes, gap_run_id),
        )
        persistence_started = perf_counter()
        await self.repository.save_roadmap(roadmap)
        persistence_ms = round((perf_counter() - persistence_started) * 1000, 3)
        await self.repository.replace_run(
            validating.model_copy(
                update={
                    "status": "COMPLETED",
                    "output_roadmap_id": roadmap_id,
                    "latency_ms": round((perf_counter() - started) * 1000, 3),
                    "provider_latency_ms": result.metadata.latency_ms,
                    "validation_latency_ms": validation_ms,
                    "persistence_latency_ms": persistence_ms,
                    "prompt_tokens": result.metadata.prompt_tokens,
                    "completion_tokens": result.metadata.completion_tokens,
                    "reasoning_tokens": result.metadata.reasoning_tokens,
                    "total_tokens": result.metadata.total_tokens,
                    "completed_at": datetime.now(UTC),
                }
            )
        )
        return roadmap

    async def _failed_run(
        self,
        student_id: str,
        gap_run_id: str,
        identity: str,
        envelopes: list[Envelope],
        retrieval_ms: float,
        status: str,
        category: str,
    ) -> None:
        now = datetime.now(UTC)
        await self.repository.save_run(
            GenerationRun(
                run_id=f"generation_{uuid4().hex}",
                student_id=student_id,
                model_id=self.gateway.model_id,
                gap_run_id=gap_run_id,
                retrieval_trace_ids=[item.bundle.trace_id for item in envelopes],
                input_evidence_ids=sorted(
                    {value for item in envelopes for value in item.evidence_ids}
                ),
                request_identity=identity,
                retrieval_latency_ms=retrieval_ms,
                status=status,  # type: ignore[arg-type]
                error_category=category,
                created_at=now,
                completed_at=now,
            )
        )

    async def _validation_failure(
        self, run: GenerationRun, started: float, status: str, category: str
    ) -> None:
        await self.repository.replace_run(
            run.model_copy(
                update={
                    "status": status,
                    "error_category": category,
                    "latency_ms": round((perf_counter() - started) * 1000, 3),
                    "completed_at": datetime.now(UTC),
                }
            )
        )

    async def get(self, student_id: str, roadmap_id: str) -> Roadmap:
        value = await self.repository.get(student_id, roadmap_id)
        if value is None:
            raise ApplicationError("ROADMAP_NOT_FOUND")
        return value

    async def list(self, student_id: str, limit: int) -> RoadmapList:
        return RoadmapList(items=await self.repository.list(student_id, limit))

    async def evidence(self, student_id: str, roadmap_id: str) -> RoadmapEvidenceResponse:
        value = await self.get(student_id, roadmap_id)
        return RoadmapEvidenceResponse(
            roadmap_id=value.roadmap_id,
            retrieval_trace_ids=value.retrieval_trace_ids,
            evidence=value.evidence,
        )
