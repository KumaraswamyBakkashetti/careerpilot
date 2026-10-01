"""Canonical graph verification against the dedicated local Neo4j test service."""

import os

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.knowledge import GraphWriter, Neo4jKnowledgeRepository
from app.infrastructure.mongodb import MongoDBAdapter
from app.infrastructure.neo4j import Neo4jAdapter
from app.main import create_app
from app.modules.knowledge.dataset import load_dataset
from app.modules.knowledge.models import assertion_id
from tests.test_integration import isolated_settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("CP_RUN_INTEGRATION") != "1",
        reason="Opt-in isolated databases required; see README",
    ),
]


async def initialized() -> tuple[Neo4jAdapter, GraphWriter, Neo4jKnowledgeRepository]:
    adapter = Neo4jAdapter(isolated_settings())
    await adapter.start()
    await adapter.ping()
    writer = GraphWriter(adapter)
    await writer.schema()
    await writer.ingest(load_dataset())
    return adapter, writer, Neo4jKnowledgeRepository(adapter)


async def test_real_graph_counts_constraints_and_invariants() -> None:
    adapter, writer, _ = await initialized()
    try:
        inspection = await writer.inspect()
        assert inspection["nodes"] == {
            "Skill": 20,
            "Role": 5,
            "Company": 1,
            "CompanyRole": 1,
            "Resource": 4,
            "InterviewTopic": 5,
        }
        assert inspection["relationships"] == {
            "REQUIRES_SKILL": 42,
            "OFFERS_ROLE": 1,
            "BASED_ON": 1,
            "COVERS_TOPIC": 4,
            "TEACHES_SKILL": 9,
            "ASSESSES_SKILL": 10,
        }
        assert inspection["invariants"] == "passed"
        assert adapter.driver is not None
        async with adapter.driver.session(database=adapter.settings.neo4j_database) as session:
            result = await session.run(
                "SHOW CONSTRAINTS YIELD name WHERE name STARTS WITH 'cp_' RETURN count(*) AS count"
            )
            assert (await result.single())["count"] == 15
    finally:
        await adapter.close()


async def test_real_queries_provenance_and_company_context() -> None:
    adapter, _, repository = await initialized()
    try:
        roles = await repository.list_entities("Role", "developer", 50, 0)
        assert [role.id for role in roles.items] == [
            "role_backend_developer",
            "role_frontend_developer",
        ]
        skills = await repository.related(
            "role_backend_developer", "Role", "REQUIRES_SKILL", False, 50, 0
        )
        assert skills is not None and len(skills.items) == 10
        python = next(item for item in skills.items if item.entity.id == "skill_python")
        assert python.evidence.assertion.importance == "CORE"
        assert python.evidence.provenance[0].source.id == "source_curated"
        resources = await repository.related("skill_python", "Skill", "TEACHES_SKILL", True, 50, 0)
        topics = await repository.related("skill_python", "Skill", "ASSESSES_SKILL", True, 50, 0)
        assert resources is not None and [item.entity.id for item in resources.items] == [
            "resource_python"
        ]
        assert topics is not None and [item.entity.id for item in topics.items] == [
            "topic_python_collections"
        ]
        evidence = await repository.evidence(
            assertion_id("role_backend_developer", "REQUIRES_SKILL", "skill_python")
        )
        assert evidence is not None and evidence.dataset_version == "careerpilot-knowledge-v1"
        context = await repository.company_context("companyrole_demo_backend")
        assert context is not None and context.company.entity.synthetic is True
        assert context.generic_role.entity.id == "role_backend_developer"
    finally:
        await adapter.close()


async def test_repeated_ingestion_is_idempotent_and_failed_transaction_rolls_back() -> None:
    adapter, writer, _ = await initialized()
    assert adapter.driver is not None
    try:
        before = await writer.inspect()
        second = await writer.ingest(load_dataset())
        after = await writer.inspect()
        assert second["nodes"] == before["nodes"] == after["nodes"]
        assert second["relationships"] == before["relationships"] == after["relationships"]
        async with adapter.driver.session(database=adapter.settings.neo4j_database) as session:
            lock_result = await session.run(
                "MATCH (d:KnowledgeDataset {id:$id}) RETURN d.lock AS lock",
                {"id": "careerpilot_core"},
            )
            old_lock = (await lock_result.single())["lock"]

            async def fail_after_writes(tx: object) -> None:
                await writer._write(tx, load_dataset())  # type: ignore[arg-type]
                raise RuntimeError("induced rollback")

            with pytest.raises(RuntimeError, match="induced rollback"):
                await session.execute_write(fail_after_writes)
            lock_result = await session.run(
                "MATCH (d:KnowledgeDataset {id:$id}) RETURN d.lock AS lock",
                {"id": "careerpilot_core"},
            )
            assert (await lock_result.single())["lock"] == old_lock
        assert (await writer.inspect())["invariants"] == "passed"
    finally:
        await adapter.close()


def test_real_fastapi_knowledge_path() -> None:
    settings = isolated_settings()
    mongo, neo = MongoDBAdapter(settings), Neo4jAdapter(settings)
    with TestClient(create_app(settings, {"mongodb": mongo, "neo4j": neo})) as client:
        response = client.get("/api/v1/knowledge/roles/role_backend_developer/skills")
        assert response.status_code == 200
        body = response.json()
        assert body["entity"]["id"] == "role_backend_developer"
        assert any(item["entity"]["id"] == "skill_python" for item in body["items"])
        assert body["items"][0]["evidence"]["provenance"]
