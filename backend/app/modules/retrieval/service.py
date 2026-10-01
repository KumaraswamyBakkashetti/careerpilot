import asyncio
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from app.core.errors import ApplicationError
from app.infrastructure.retrieval_index import (
    FaissIndexStore,
    IndexIncompatibleError,
    IndexUnavailableError,
)
from app.modules.knowledge.models import RelatedEntity
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.retrieval.models import (
    EvidenceBundle,
    ProvenanceRef,
    Rejection,
    RetrievalGraphEvidence,
    RetrievalRequest,
    RetrievalTask,
    RetrievalTrace,
    Sufficiency,
    VectorEvidence,
)
from app.modules.retrieval.planner import RetrievalPlanner, build_skill_query
from app.modules.retrieval.repository import RetrievalTraceRepository
from app.modules.student.repository import StudentRepository


def graph_evidence(value: RelatedEntity) -> RetrievalGraphEvidence:
    assertion = value.evidence.assertion
    return RetrievalGraphEvidence(
        entity_id=value.entity.id,
        entity_name=value.entity.name,
        relationship_type=assertion.type,
        assertion_id=assertion.id,
        importance=assertion.importance or "UNSPECIFIED",
        source_ids=sorted({item.citation.source_id for item in value.evidence.provenance}),
        dataset_version=value.evidence.dataset_version,
    )


class RetrievalService:
    def __init__(
        self,
        knowledge: KnowledgeRepository,
        students: StudentRepository,
        traces: RetrievalTraceRepository,
        index: FaissIndexStore,
        default_top_k: int,
        max_top_k: int,
    ) -> None:
        self.knowledge = knowledge
        self.students = students
        self.traces = traces
        self.index = index
        self.default_top_k = default_top_k
        self.max_top_k = max_top_k
        self.planner = RetrievalPlanner()

    async def initialize(self) -> None:
        await self.traces.initialize()

    def _top_k(self, requested: int | None) -> int:
        value = requested or self.default_top_k
        if value > self.max_top_k:
            raise ApplicationError("RETRIEVAL_LIMIT_EXCEEDED")
        return value

    async def _search(
        self, query: str, top_k: int, skill_id: str | None = None
    ) -> tuple[list[VectorEvidence], list[tuple[str, str]]]:
        try:
            return await asyncio.to_thread(self.index.search, query, top_k, skill_id)
        except IndexIncompatibleError as exc:
            raise ApplicationError("RETRIEVAL_INDEX_INCOMPATIBLE") from exc
        except IndexUnavailableError as exc:
            raise ApplicationError("RETRIEVAL_INDEX_UNAVAILABLE") from exc

    async def execute(
        self,
        student_id: str,
        request_id: str,
        request: RetrievalRequest,
        task_override: RetrievalTask | None = None,
        gap_context: dict[str, str] | None = None,
        allow_vector_fallback: bool = False,
        trusted_skill_name: str | None = None,
    ) -> EvidenceBundle:
        started = perf_counter()
        strategy = self.planner.plan(request)
        graph: list[RetrievalGraphEvidence] = []
        vectors: list[VectorEvidence] = []
        rejected: list[tuple[str, str]] = []
        graph_ops: list[str] = []
        queries: list[str] = []
        target: dict[str, str] | None = None
        if strategy == "GRAPH_ONLY":
            assert request.role_id is not None
            related = await self.knowledge.related(
                request.role_id, "Role", "REQUIRES_SKILL", False, 100, 0
            )
            graph_ops.append(f"Role({request.role_id})-[:REQUIRES_SKILL]->Skill")
            if related is None:
                raise ApplicationError("TARGET_ROLE_NOT_FOUND")
            graph = [graph_evidence(item) for item in related.items]
            target = {"role_id": related.entity.id, "role_name": related.entity.name}
        else:
            assert request.skill_id is not None
            try:
                skill = await self.knowledge.entity(request.skill_id, "Skill")
            except ApplicationError:
                if not allow_vector_fallback or trusted_skill_name is None:
                    raise
                skill = None
                strategy = "VECTOR_ONLY_FALLBACK"
                graph_ops.append("canonical_skill_lookup:DEPENDENCY_UNAVAILABLE")
            if skill is None and trusted_skill_name is None:
                raise ApplicationError("SKILL_NOT_FOUND")
            skill_name = skill.name if skill is not None else trusted_skill_name
            assert skill_name is not None
            query = request.query or build_skill_query(skill_name)
            queries.append(query)
            if strategy == "GRAPH_THEN_VECTOR":
                try:
                    related = await self.knowledge.related(
                        request.skill_id, "Skill", "TEACHES_SKILL", True, 100, 0
                    )
                    graph_ops.append(f"Resource-[:TEACHES_SKILL]->Skill({request.skill_id})")
                    if related is not None:
                        graph = [graph_evidence(item) for item in related.items]
                except ApplicationError:
                    if not allow_vector_fallback:
                        raise
                    strategy = "VECTOR_ONLY_FALLBACK"
                    graph_ops.append("resource_skill_graph:DEPENDENCY_UNAVAILABLE")
            vectors, rejected = await self._search(
                query, self._top_k(request.top_k), request.skill_id
            )
            target = {"skill_id": request.skill_id, "skill_name": skill_name}
        if graph and (vectors or strategy == "GRAPH_ONLY"):
            sufficiency = Sufficiency(status="SUFFICIENT", reasons=["REQUIRED_EVIDENCE_PRESENT"])
        elif graph or vectors:
            sufficiency = Sufficiency(status="PARTIAL", reasons=["ONE_EVIDENCE_CHANNEL_MISSING"])
        else:
            sufficiency = Sufficiency(status="INSUFFICIENT", reasons=["NO_VALIDATED_EVIDENCE"])
        trace_id = f"trace_{uuid4().hex}"
        versions = {
            "sufficiency": sufficiency.rule_version,
            "knowledge": graph[0].dataset_version if graph else "not_observed",
        }
        if vectors:
            versions.update(
                {
                    "index": vectors[0].index_version,
                    "embedding": vectors[0].embedding_model,
                    "chunking": self.index.manifest.chunking_version,
                }
            )
        provenance = [
            ProvenanceRef(
                evidence_type="GRAPH",
                evidence_id=item.assertion_id,
                source_id=item.source_ids[0],
            )
            for item in graph
            if item.source_ids
        ] + [
            ProvenanceRef(
                evidence_type="VECTOR",
                evidence_id=item.chunk_id,
                source_id=item.source_id,
                resource_id=item.resource_id,
            )
            for item in vectors
        ]
        task = task_override or request.task
        bundle = EvidenceBundle(
            task=task,
            retrieval_strategy=strategy,
            student_context={"student_id": student_id},
            target_context=target,
            gap_context=gap_context,
            graph_evidence=graph,
            vector_evidence=vectors,
            provenance=provenance,
            sufficiency=sufficiency,
            trace_id=trace_id,
            versions=versions,
        )
        await self.traces.save(
            RetrievalTrace(
                trace_id=trace_id,
                request_id=request_id,
                student_id=student_id,
                task=task,
                strategy=strategy,
                graph_operations=graph_ops,
                vector_queries=queries,
                candidate_count=len(vectors) + len(rejected),
                selected_evidence_ids=[
                    *[item.assertion_id for item in graph],
                    *[item.chunk_id for item in vectors],
                ],
                rejected_evidence=[
                    Rejection(evidence_id=identifier, reason=reason)
                    for identifier, reason in rejected
                ],
                sufficiency=sufficiency.status,
                duration_ms=round((perf_counter() - started) * 1000, 3),
                knowledge_dataset_version=versions["knowledge"],
                embedding_model=versions.get("embedding"),
                index_version=versions.get("index"),
                chunking_version=versions.get("chunking"),
                created_at=datetime.now(UTC),
            )
        )
        return bundle

    async def gap_evidence(
        self, student_id: str, request_id: str, run_id: str, skill_id: str, top_k: int | None
    ) -> EvidenceBundle:
        run = await self.students.gap(student_id, run_id)
        if run is None:
            raise ApplicationError("GAP_ANALYSIS_NOT_FOUND")
        gap = next((item for item in run.items if item.skill_id == skill_id), None)
        if gap is None:
            raise ApplicationError("SKILL_NOT_FOUND")
        return await self.execute(
            student_id,
            request_id,
            RetrievalRequest(task="SKILL_RESOURCES", skill_id=skill_id, top_k=top_k),
            task_override="GAP_RESOURCES",
            gap_context={
                "gap_run_id": run_id,
                "status": gap.status,
                "importance": gap.importance,
                "graph_assertion_id": gap.graph_assertion_id,
            },
            allow_vector_fallback=True,
            trusted_skill_name=gap.skill_name,
        )

    async def trace(self, student_id: str, trace_id: str) -> RetrievalTrace:
        value = await self.traces.get(student_id, trace_id)
        if value is None:
            raise ApplicationError("RETRIEVAL_TRACE_NOT_FOUND")
        return value
