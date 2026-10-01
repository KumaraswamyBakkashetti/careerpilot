from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

CanonicalId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{2,79}$")]
RetrievalStrategy = Literal[
    "GRAPH_ONLY",
    "VECTOR_ONLY",
    "GRAPH_THEN_VECTOR",
    "PARALLEL_HYBRID",
    "VECTOR_ONLY_FALLBACK",
]
SufficiencyStatus = Literal["SUFFICIENT", "PARTIAL", "INSUFFICIENT"]
RetrievalTask = Literal["ROLE_REQUIREMENTS", "SKILL_RESOURCES", "GAP_RESOURCES"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CanonicalResource(StrictModel):
    resource_id: CanonicalId
    source_id: CanonicalId
    content_ref: CanonicalId
    name: str
    url: str
    resource_type: Literal["DOCUMENTATION"] = "DOCUMENTATION"
    text: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    skill_ids: list[CanonicalId]
    corpus_version: str


class ResourceChunk(StrictModel):
    chunk_id: CanonicalId
    resource_id: CanonicalId
    source_id: CanonicalId
    sequence: int = Field(ge=0)
    text: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunking_version: str
    metadata: dict[str, str | list[str]]
    created_at: datetime


class IndexManifest(StrictModel):
    index_version: str
    build_version: Literal["faiss-build-v1"] = "faiss-build-v1"
    embedding_model: str
    embedding_revision: str
    embedding_dimension: int = Field(gt=0)
    normalized: bool
    similarity: Literal["cosine_via_normalized_inner_product"]
    chunking_version: str
    chunk_size: int
    chunk_overlap: int
    knowledge_dataset_version: str
    resource_corpus_version: str
    corpus_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    resource_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    index_type: Literal["IndexFlatIP"] = "IndexFlatIP"
    index_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    metadata_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    embedding_duration_ms: float = Field(ge=0)
    build_duration_ms: float = Field(ge=0)


class VectorEvidence(StrictModel):
    chunk_id: CanonicalId
    resource_id: CanonicalId
    source_id: CanonicalId
    text: str
    similarity_score: float
    rank: int = Field(ge=1)
    metadata: dict[str, str | list[str]]
    index_version: str
    embedding_model: str


class RetrievalGraphEvidence(StrictModel):
    entity_id: CanonicalId
    entity_name: str
    relationship_type: str
    assertion_id: CanonicalId
    importance: str
    source_ids: list[CanonicalId]
    dataset_version: str


class ProvenanceRef(StrictModel):
    evidence_type: Literal["GRAPH", "VECTOR"]
    evidence_id: CanonicalId
    source_id: CanonicalId
    resource_id: CanonicalId | None = None


class Sufficiency(StrictModel):
    status: SufficiencyStatus
    rule_version: Literal["retrieval-sufficiency-v1"] = "retrieval-sufficiency-v1"
    reasons: list[str]


class EvidenceBundle(StrictModel):
    task: RetrievalTask
    retrieval_strategy: RetrievalStrategy
    student_context: dict[str, str] | None = None
    target_context: dict[str, str] | None = None
    gap_context: dict[str, str] | None = None
    graph_evidence: list[RetrievalGraphEvidence]
    vector_evidence: list[VectorEvidence]
    provenance: list[ProvenanceRef]
    sufficiency: Sufficiency
    trace_id: str = Field(pattern=r"^trace_[a-f0-9]{32}$")
    versions: dict[str, str]


class Rejection(StrictModel):
    evidence_id: CanonicalId
    reason: str


class RetrievalTrace(StrictModel):
    trace_id: str = Field(pattern=r"^trace_[a-f0-9]{32}$")
    request_id: str
    student_id: str | None = None
    task: str
    strategy: RetrievalStrategy
    graph_operations: list[str]
    vector_queries: list[str]
    candidate_count: int
    selected_evidence_ids: list[CanonicalId]
    rejected_evidence: list[Rejection]
    sufficiency: SufficiencyStatus
    duration_ms: float
    knowledge_dataset_version: str
    embedding_model: str | None = None
    index_version: str | None = None
    chunking_version: str | None = None
    created_at: datetime


class RetrievalRequest(StrictModel):
    task: Literal["ROLE_REQUIREMENTS", "SKILL_RESOURCES"]
    role_id: CanonicalId | None = None
    skill_id: CanonicalId | None = None
    query: str | None = Field(default=None, min_length=2, max_length=300)
    top_k: int | None = Field(default=None, ge=1, le=100)
