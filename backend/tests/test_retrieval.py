from pathlib import Path

import numpy as np
import pytest

from app.core.errors import ApplicationError
from app.infrastructure.retrieval_index import (
    FaissIndexStore,
    IndexIncompatibleError,
    IndexUnavailableError,
)
from app.modules.retrieval.corpus import chunk_resource, corpus_fingerprint, load_corpus
from app.modules.retrieval.models import RetrievalRequest
from app.modules.retrieval.planner import RetrievalPlanner, build_skill_query
from app.modules.retrieval.repository import InMemoryRetrievalTraceRepository
from app.modules.retrieval.service import RetrievalService


class FakeEmbedding:
    dimension = 4
    model_id = "test/deterministic"
    model_version = "v1"

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        values = np.asarray([self._vector(text) for text in texts], dtype=np.float32)
        norms = np.linalg.norm(values, axis=1, keepdims=True)
        return values / np.maximum(norms, 1e-9)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([text])[0]

    @staticmethod
    def _vector(text: str) -> list[float]:
        lowered = text.casefold()
        return [
            float(lowered.count("python") + lowered.count("list")),
            float(lowered.count("sql") + lowered.count("table")),
            float(lowered.count("html") + lowered.count("web")),
            float(lowered.count("test") + lowered.count("assert")),
        ]


@pytest.fixture
def corpus() -> tuple[str, list]:
    return load_corpus(Path(__file__).resolve().parents[1] / "knowledge_data")


def test_corpus_matches_graph_resources_and_has_no_private_content(
    corpus: tuple[str, list],
) -> None:
    version, resources = corpus
    assert version == "careerpilot-knowledge-v1"
    assert {item.resource_id for item in resources} == {
        "resource_python",
        "resource_postgres",
        "resource_mdn",
        "resource_pytest",
    }
    assert all(item.source_id and item.skill_ids for item in resources)
    assert all("resume" not in item.text.casefold() for item in resources)


def test_chunking_is_stable_and_overlap_is_bounded(corpus: tuple[str, list]) -> None:
    resource = corpus[1][1]
    first = chunk_resource(resource, 220, 40)
    second = chunk_resource(resource, 220, 40)
    assert [item.chunk_id for item in first] == [item.chunk_id for item in second]
    assert [item.content_hash for item in first] == [item.content_hash for item in second]
    assert all(len(item.text) <= 220 for item in first)
    with pytest.raises(ValueError):
        chunk_resource(resource, 100, 100)


def test_planner_and_query_builder_are_deterministic() -> None:
    planner = RetrievalPlanner()
    assert (
        planner.plan(RetrievalRequest(task="ROLE_REQUIREMENTS", role_id="role_backend_developer"))
        == "GRAPH_ONLY"
    )
    assert (
        planner.plan(RetrievalRequest(task="SKILL_RESOURCES", skill_id="skill_python"))
        == "GRAPH_THEN_VECTOR"
    )
    assert (
        planner.plan(
            RetrievalRequest(
                task="SKILL_RESOURCES", skill_id="skill_python", query="python collections"
            )
        )
        == "VECTOR_ONLY"
    )
    assert build_skill_query("Python", "Backend Developer") == (
        "Learn and practice Python for the Backend Developer role using canonical documentation."
    )


def test_real_faiss_build_load_search_filter_and_idempotency(
    tmp_path: Path, corpus: tuple[str, list]
) -> None:
    version, resources = corpus
    chunks = [item for resource in resources for item in chunk_resource(resource, 300, 40)]
    store = FaissIndexStore(tmp_path, FakeEmbedding())
    first = store.build(resources, chunks, version, resources[0].corpus_version, 300, 40)
    second = store.build(resources, chunks, version, resources[0].corpus_version, 300, 40)
    assert first.index_version == second.index_version
    assert len(list(tmp_path.glob("index-*"))) == 1
    loaded = FaissIndexStore(tmp_path, FakeEmbedding())
    manifest = loaded.load(
        version, resources[0].corpus_version, corpus_fingerprint(resources), 300, 40
    )
    assert manifest.chunk_count == len(chunks)
    results, _ = loaded.search("joining SQL tables", 3, "skill_sql")
    assert results
    assert all(item.resource_id == "resource_postgres" for item in results)
    assert all(item.source_id == "source_postgres" for item in results)
    assert results[0].similarity_score >= results[-1].similarity_score


def test_faiss_missing_corrupt_and_incompatible_fail_safely(
    tmp_path: Path, corpus: tuple[str, list]
) -> None:
    version, resources = corpus
    store = FaissIndexStore(tmp_path, FakeEmbedding())
    with pytest.raises(IndexUnavailableError):
        store.load(version, resources[0].corpus_version, corpus_fingerprint(resources), 300, 40)
    chunks = [item for resource in resources for item in chunk_resource(resource, 300, 40)]
    store.build(resources, chunks, version, resources[0].corpus_version, 300, 40)
    with pytest.raises(IndexIncompatibleError):
        FaissIndexStore(tmp_path, FakeEmbedding()).load(
            version, resources[0].corpus_version, corpus_fingerprint(resources), 301, 40
        )
    pointer = __import__("json").loads((tmp_path / "active.json").read_text("utf-8"))
    (tmp_path / pointer["directory"] / "vectors.faiss").write_bytes(b"broken")
    with pytest.raises(IndexUnavailableError):
        FaissIndexStore(tmp_path, FakeEmbedding()).load(
            version, resources[0].corpus_version, corpus_fingerprint(resources), 300, 40
        )


class EmptyKnowledge:
    async def entity(self, identifier: str, kind: str):
        from app.modules.knowledge.models import Entity

        return Entity(
            id=identifier,
            kind=kind,
            name="Python",
            description="Canonical Python programming skill.",
            source_ids=["source_curated"],
            aliases=[],
            category="Programming",
        )

    async def related(self, *args, **kwargs):
        return None


class EmptyStudents:
    async def gap(self, student_id: str, run_id: str):
        return None


class UnavailableKnowledge(EmptyKnowledge):
    async def entity(self, identifier: str, kind: str):
        raise ApplicationError("DEPENDENCY_UNAVAILABLE")


class SearchIndex:
    class Manifest:
        chunking_version = "deterministic-structure-v1"

    manifest = Manifest()

    def search(self, query: str, top_k: int, skill_id: str | None = None):
        from app.modules.retrieval.models import VectorEvidence

        return [
            VectorEvidence(
                chunk_id="chunk_0123456789abcdef0123456789abcdef",
                resource_id="resource_python",
                source_id="source_python",
                text="Python lists and dictionaries support collection operations.",
                similarity_score=0.8,
                rank=1,
                metadata={"skill_ids": ["skill_python"]},
                index_version="retrieval-test",
                embedding_model="test/model",
            )
        ], []


@pytest.mark.asyncio
async def test_vector_only_bundle_is_partial_without_graph_and_trace_is_owner_scoped() -> None:
    traces = InMemoryRetrievalTraceRepository()
    service = RetrievalService(
        EmptyKnowledge(), EmptyStudents(), traces, SearchIndex(), default_top_k=3, max_top_k=10
    )
    bundle = await service.execute(
        "student_0123456789abcdef0123456789abcdef",
        "request-1",
        RetrievalRequest(
            task="SKILL_RESOURCES", skill_id="skill_python", query="python collections"
        ),
    )
    assert bundle.retrieval_strategy == "VECTOR_ONLY"
    assert bundle.sufficiency.status == "PARTIAL"
    assert bundle.vector_evidence[0].source_id == "source_python"
    assert bundle.provenance[0].resource_id == "resource_python"
    trace = await service.trace("student_0123456789abcdef0123456789abcdef", bundle.trace_id)
    assert trace.vector_queries == ["python collections"]
    with pytest.raises(ApplicationError):
        await service.trace("student_ffffffffffffffffffffffffffffffff", bundle.trace_id)


@pytest.mark.asyncio
async def test_explicit_vector_fallback_is_never_labelled_graph_verified() -> None:
    service = RetrievalService(
        UnavailableKnowledge(),
        EmptyStudents(),
        InMemoryRetrievalTraceRepository(),
        SearchIndex(),
        default_top_k=3,
        max_top_k=10,
    )
    bundle = await service.execute(
        "student_0123456789abcdef0123456789abcdef",
        "request-2",
        RetrievalRequest(task="SKILL_RESOURCES", skill_id="skill_python"),
        allow_vector_fallback=True,
        trusted_skill_name="Python",
    )
    assert bundle.retrieval_strategy == "VECTOR_ONLY_FALLBACK"
    assert bundle.sufficiency.status == "PARTIAL"
    assert bundle.graph_evidence == []
