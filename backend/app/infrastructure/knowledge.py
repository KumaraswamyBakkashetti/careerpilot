"""All graph query/schema/write behavior lives here, outside domain/application logic."""

import asyncio
import json
import logging
from collections import Counter
from time import perf_counter
from typing import Any

from neo4j import AsyncManagedTransaction
from neo4j.exceptions import AuthError, DriverError, Neo4jError
from pydantic import ValidationError

from app.core.errors import ApplicationError
from app.infrastructure.neo4j import Neo4jAdapter
from app.modules.knowledge.dataset import dataset_hash
from app.modules.knowledge.models import (
    ENDPOINTS,
    Assertion,
    CompanyContext,
    Dataset,
    Entity,
    EntityPage,
    GraphEvidence,
    Kind,
    RelatedEntity,
    RelationsPage,
    RelationType,
    Source,
    SupportedCitation,
    assertion_id,
)

KINDS = ("Skill", "Role", "Company", "CompanyRole", "Resource", "InterviewTopic")


class Neo4jKnowledgeRepository:
    def __init__(self, adapter: Neo4jAdapter) -> None:
        self.adapter = adapter

    async def _query(self, query: str, parameters: dict[str, object]) -> list[dict[str, Any]]:
        start = perf_counter()
        try:
            if self.adapter.driver is None:
                raise ApplicationError()
            async with asyncio.timeout(self.adapter.settings.dependency_timeout_seconds):
                async with self.adapter.driver.session(
                    database=self.adapter.settings.neo4j_database, default_access_mode="READ"
                ) as session:
                    result = await session.run(query, parameters)
                    records = await result.data()
            logging.getLogger("careerpilot.knowledge").info(
                "graph_query_completed",
                extra={
                    "operation": "knowledge_read",
                    "result_count": len(records),
                    "duration_ms": round((perf_counter() - start) * 1000, 2),
                },
            )
            return records
        except (DriverError, AuthError, TimeoutError) as exc:
            raise ApplicationError() from exc
        except Neo4jError as exc:
            if exc.code and exc.code.endswith("DatabaseNotFound"):
                raise ApplicationError() from exc
            raise

    @staticmethod
    def _entity(properties: dict[str, Any]) -> Entity:
        try:
            return Entity.model_validate_json(properties["payload"])
        except (KeyError, ValidationError, ValueError) as exc:
            raise ApplicationError("KNOWLEDGE_INCONSISTENT") from exc

    @staticmethod
    def _evidence(row: dict[str, Any]) -> GraphEvidence:
        try:
            assertion = Assertion.model_validate_json(row["assertion"]["payload"])
            sources = {s["id"]: Source.model_validate_json(s["payload"]) for s in row["sources"]}
            return GraphEvidence(
                assertion=assertion,
                provenance=[
                    SupportedCitation(citation=c, source=sources[c.source_id])
                    for c in assertion.provenance
                ],
                dataset_version=row["assertion"]["dataset_version"],
                path=[assertion.source_id, assertion.type, assertion.target_id],
            )
        except (KeyError, ValidationError, ValueError, TypeError) as exc:
            raise ApplicationError("KNOWLEDGE_INCONSISTENT") from exc

    async def list_entities(self, kind: Kind, query: str, limit: int, offset: int) -> EntityPage:
        # Labels below come only from a closed vocabulary; data always uses parameters.
        if kind not in KINDS:
            raise ValueError("Unsupported entity kind")
        rows = await self._query(
            f"MATCH (n:KnowledgeEntity:{kind}) "
            "WHERE $query = '' OR toLower(n.name) CONTAINS toLower($query) "
            "RETURN properties(n) AS entity ORDER BY n.name, n.id SKIP $offset LIMIT $limit",
            {"query": query, "limit": limit, "offset": offset},
        )
        return EntityPage(
            items=[self._entity(r["entity"]) for r in rows], limit=limit, offset=offset
        )

    async def entity(self, identifier: str, kind: Kind) -> Entity | None:
        rows = await self._query(
            "MATCH (n:KnowledgeEntity {id: $id}) WHERE n.kind = $kind "
            "RETURN properties(n) AS entity",
            {"id": identifier, "kind": kind},
        )
        return self._entity(rows[0]["entity"]) if rows else None

    async def related(
        self,
        identifier: str,
        kind: Kind,
        relation: RelationType,
        incoming: bool,
        limit: int,
        offset: int,
    ) -> RelationsPage | None:
        if relation not in ENDPOINTS:
            raise ValueError("Unsupported relationship")
        if self.adapter.driver is None:
            raise ApplicationError()
        # Parent existence and items share one query/read snapshot, including the empty case.
        pattern = f"(n)<-[r:{relation}]-(other)" if incoming else f"(n)-[r:{relation}]->(other)"
        rows = await self._query(
            "MATCH (n:KnowledgeEntity {id: $id}) WHERE n.kind = $kind "
            "CALL (n) { "
            f"MATCH {pattern} "
            "WITH other,r ORDER BY other.name,other.id SKIP $offset LIMIT $limit "
            "OPTIONAL MATCH (s:KnowledgeSource) WHERE s.id IN r.source_ids "
            "WITH other,r,collect(properties(s)) AS sources "
            "RETURN collect({entity:properties(other),assertion:properties(r),"
            "sources:sources}) AS items "
            "} RETURN properties(n) AS parent,items",
            {"id": identifier, "kind": kind, "limit": limit, "offset": offset},
        )
        if not rows:
            return None
        return RelationsPage(
            entity=self._entity(rows[0]["parent"]),
            items=[
                RelatedEntity(entity=self._entity(row["entity"]), evidence=self._evidence(row))
                for row in rows[0]["items"]
            ],
            limit=limit,
            offset=offset,
        )

    async def evidence(self, identifier: str) -> GraphEvidence | None:
        rows = await self._query(
            "MATCH (a:KnowledgeEntity)-[r:OFFERS_ROLE|BASED_ON|REQUIRES_SKILL|"
            "TEACHES_SKILL|COVERS_TOPIC|ASSESSES_SKILL]->(b:KnowledgeEntity) WHERE r.id = $id "
            "OPTIONAL MATCH (s:KnowledgeSource) WHERE s.id IN r.source_ids "
            "RETURN properties(r) AS assertion, collect(properties(s)) AS sources",
            {"id": identifier},
        )
        return self._evidence(rows[0]) if rows else None

    async def company_context(self, identifier: str) -> CompanyContext | None:
        company = await self.related(identifier, "CompanyRole", "OFFERS_ROLE", True, 2, 0)
        generic = await self.related(identifier, "CompanyRole", "BASED_ON", False, 2, 0)
        if company is None or generic is None:
            return None
        if len(company.items) != 1 or len(generic.items) != 1:
            raise ApplicationError("KNOWLEDGE_INCONSISTENT")
        return CompanyContext(
            company_role=company.entity, company=company.items[0], generic_role=generic.items[0]
        )


class GraphWriter:
    """CLI-only writes; snapshot ownership/version hashes prevent silent overwrite."""

    def __init__(self, adapter: Neo4jAdapter) -> None:
        self.adapter = adapter

    async def schema(self) -> None:
        if self.adapter.driver is None:
            raise ApplicationError()
        async with self.adapter.driver.session(
            database=self.adapter.settings.neo4j_database
        ) as session:
            for label in (*KINDS, "KnowledgeEntity", "KnowledgeSource", "KnowledgeDataset"):
                result = await session.run(
                    f"CREATE CONSTRAINT cp_{label.lower()}_id IF NOT EXISTS "
                    f"FOR (n:{label}) REQUIRE n.id IS UNIQUE"
                )
                await result.consume()
            for relation in ENDPOINTS:
                result = await session.run(
                    f"CREATE CONSTRAINT cp_{relation.lower()}_id IF NOT EXISTS "
                    f"FOR ()-[r:{relation}]-() REQUIRE r.id IS UNIQUE"
                )
                await result.consume()

    async def ingest(self, dataset: Dataset) -> dict[str, object]:
        # Revalidate even if caller mutated an already parsed model after validation.
        validated = Dataset.model_validate(dataset.model_dump(mode="json"))
        if self.adapter.driver is None:
            raise ApplicationError()
        async with asyncio.timeout(30):
            async with self.adapter.driver.session(
                database=self.adapter.settings.neo4j_database
            ) as session:
                return await session.execute_write(self._write, validated)

    async def _write(self, tx: AsyncManagedTransaction, dataset: Dataset) -> dict[str, object]:
        parameters = {
            "owner": dataset.dataset_id,
            "version": dataset.version,
            "hash": dataset_hash(dataset),
            "validated": dataset.validated_at.isoformat(),
        }
        result = await tx.run(
            "MERGE (d:KnowledgeDataset {id:$owner}) SET d.lock=coalesce(d.lock,0)+1 "
            "RETURN d.version AS version,d.content_hash AS hash",
            parameters,
        )
        previous = await result.single()
        if (
            previous
            and previous["version"] == dataset.version
            and previous["hash"] != parameters["hash"]
        ):
            raise ValueError(
                "Dataset version is immutable; increment version for intentional updates"
            )
        if (
            previous
            and previous["version"]
            and int(previous["version"].rsplit("v", 1)[1]) > int(dataset.version.rsplit("v", 1)[1])
        ):
            raise ValueError("Dataset version downgrade is forbidden")
        entities = [
            {"id": e.id, "kind": e.kind, "name": e.name, "payload": e.model_dump_json()}
            for e in dataset.entities
        ]
        sources = [{"id": s.id, "payload": s.model_dump_json()} for s in dataset.sources]
        result = await tx.run(
            "MATCH (n) WHERE (n:KnowledgeEntity OR n:KnowledgeSource) AND n.id IN $ids "
            "AND (n.dataset_id IS NULL OR n.dataset_id <> $owner) RETURN count(n) AS conflicts",
            {**parameters, "ids": [e["id"] for e in entities] + [s["id"] for s in sources]},
        )
        record = await result.single()
        if record and record["conflicts"]:
            raise ValueError("Canonical identifier owned outside this dataset")
        result = await tx.run(
            "UNWIND $rows AS row MATCH (n:KnowledgeEntity {id:row.id}) "
            "WHERE n.kind <> row.kind RETURN count(n) AS conflicts",
            {"rows": entities},
        )
        record = await result.single()
        if record and record["conflicts"]:
            raise ValueError("Canonical entity kind is immutable")
        result = await tx.run(
            "UNWIND $rows AS row MERGE (s:KnowledgeSource {id:row.id}) "
            "SET s.payload=row.payload,s.dataset_id=$owner,s.dataset_version=$version",
            {**parameters, "rows": sources},
        )
        await result.consume()
        for kind in KINDS:
            result = await tx.run(
                f"UNWIND $rows AS row MERGE (n:KnowledgeEntity:{kind} {{id:row.id}}) "
                "SET n.kind=row.kind,n.name=row.name,n.payload=row.payload,"
                "n.dataset_id=$owner,n.dataset_version=$version",
                {**parameters, "rows": [e for e in entities if e["kind"] == kind]},
            )
            await result.consume()
        for relation in ENDPOINTS:
            rows = [
                {
                    "id": a.id,
                    "from": a.source_id,
                    "to": a.target_id,
                    "payload": a.model_dump_json(),
                    "source_ids": [c.source_id for c in a.provenance],
                    "importance": a.importance,
                }
                for a in dataset.assertions
                if a.type == relation
            ]
            result = await tx.run(
                "UNWIND $rows AS row MATCH (a:KnowledgeEntity {id:row.from}),"
                "(b:KnowledgeEntity {id:row.to}) "
                f"MERGE (a)-[r:{relation} {{id:row.id}}]->(b) "
                "SET r.payload=row.payload,r.source_ids=row.source_ids,r.importance=row.importance,"
                "r.dataset_id=$owner,r.dataset_version=$version RETURN count(r) AS written",
                {**parameters, "rows": rows},
            )
            record = await result.single()
            if record is None or record["written"] != len(rows):
                raise ValueError("Ingestion endpoint mismatch")
        # Prune only this dataset's omitted assertions; unrelated graph facts are never touched.
        result = await tx.run(
            "MATCH ()-[r]->() WHERE r.dataset_id=$owner AND NOT r.id IN $ids DELETE r",
            {**parameters, "ids": [a.id for a in dataset.assertions]},
        )
        await result.consume()
        result = await tx.run(
            "MATCH (n) WHERE (n:KnowledgeEntity OR n:KnowledgeSource) AND n.dataset_id=$owner "
            "AND NOT n.id IN $ids DELETE n",  # External relationships make removal fail/rollback.
            {
                **parameters,
                "ids": [e.id for e in dataset.entities] + [s.id for s in dataset.sources],
            },
        )
        await result.consume()
        result = await tx.run(
            "MATCH (d:KnowledgeDataset {id:$owner}) SET d.version=$version,"
            "d.content_hash=$hash,d.validated_at=$validated",
            parameters,
        )
        await result.consume()
        return {
            "dataset_version": dataset.version,
            "content_hash": parameters["hash"],
            "nodes": dict(Counter(e.kind for e in dataset.entities)),
            "relationships": dict(Counter(a.type for a in dataset.assertions)),
            "sources": len(dataset.sources),
        }

    async def inspect(self) -> dict[str, object]:
        repo = Neo4jKnowledgeRepository(self.adapter)
        nodes = await repo._query(
            "MATCH (n:KnowledgeEntity) RETURN n.kind AS kind,count(n) AS count", {}
        )
        relations = await repo._query(
            "MATCH (:KnowledgeEntity)-[r]->(:KnowledgeEntity) "
            "RETURN type(r) AS kind,count(r) AS count",
            {},
        )
        # Parse full snapshot and re-run all semantic invariants on the graph itself.
        rows = await repo._query(
            "MATCH (d:KnowledgeDataset {id:$owner}) "
            "CALL () { MATCH (n:KnowledgeEntity {dataset_id:$owner}) "
            "RETURN collect(n.payload) AS entities } "
            "CALL () { MATCH (s:KnowledgeSource {dataset_id:$owner}) "
            "RETURN collect(s.payload) AS sources } "
            "CALL () { MATCH ()-[r]->() WHERE r.dataset_id=$owner "
            "RETURN collect(r.payload) AS assertions } "
            "RETURN d.version AS version,d.validated_at AS validated,entities,sources,assertions",
            {"owner": "careerpilot_core"},
        )
        if not rows:
            raise ValueError("No ingested dataset manifest")
        row = rows[0]
        snapshot = Dataset.model_validate(
            {
                "version": row["version"],
                "validated_at": row["validated"],
                **{
                    key: [json.loads(item) for item in row[key]]
                    for key in ("entities", "sources", "assertions")
                },
            }
        )
        actual_nodes = await repo._query(
            "MATCH (n:KnowledgeEntity {dataset_id:$owner}) "
            "RETURN properties(n) AS node,labels(n) AS labels",
            {"owner": "careerpilot_core"},
        )
        for actual in actual_nodes:
            entity = Entity.model_validate_json(actual["node"]["payload"])
            if (
                actual["node"]["id"] != entity.id
                or actual["node"]["kind"] != entity.kind
                or actual["node"]["name"] != entity.name
                or set(actual["labels"]) != {"KnowledgeEntity", entity.kind}
            ):
                raise ValueError("Graph node properties disagree with validated payload")
        actual_edges = await repo._query(
            "MATCH (a)-[r]->(b) WHERE r.dataset_id=$owner "
            "RETURN a.id AS source,b.id AS target,type(r) AS type,properties(r) AS edge",
            {"owner": "careerpilot_core"},
        )
        for actual in actual_edges:
            edge = actual["edge"]
            assertion = Assertion.model_validate_json(edge["payload"])
            if (
                actual["source"] != assertion.source_id
                or actual["target"] != assertion.target_id
                or actual["type"] != assertion.type
                or edge["id"] != assertion.id
                or edge.get("importance") != assertion.importance
                or edge["source_ids"] != [c.source_id for c in assertion.provenance]
            ):
                raise ValueError("Graph relationship disagrees with validated payload")
        actual_sources = await repo._query(
            "MATCH (n:KnowledgeSource {dataset_id:$owner}) RETURN properties(n) AS source",
            {"owner": "careerpilot_core"},
        )
        for actual in actual_sources:
            source = Source.model_validate_json(actual["source"]["payload"])
            if actual["source"]["id"] != source.id:
                raise ValueError("Graph source identity mismatch")
        manifests = await repo._query(
            "MATCH (d:KnowledgeDataset {id:$owner}) RETURN d.content_hash AS hash",
            {"owner": "careerpilot_core"},
        )
        if dataset_hash(snapshot) != manifests[0]["hash"]:
            raise ValueError("Stored snapshot disagrees with manifest content hash")
        orphans = await repo._query(
            "MATCH (n:KnowledgeEntity {dataset_id:$owner}) WHERE NOT (n)--() "
            "RETURN count(n) AS count",
            {"owner": "careerpilot_core"},
        )
        if orphans[0]["count"]:
            raise ValueError("Canonical dataset contains disconnected entities")
        bad = await repo._query(
            "MATCH (a:KnowledgeEntity)-[r]->(b:KnowledgeEntity) WHERE r.dataset_id=$owner "
            "AND (r.id IS NULL OR r.payload IS NULL OR size(coalesce(r.source_ids,[]))=0) "
            "RETURN count(r) AS count",
            {"owner": "careerpilot_core"},
        )
        if bad[0]["count"]:
            raise ValueError("Graph contains incomplete evidence")
        return {
            "nodes": {r["kind"]: r["count"] for r in nodes},
            "relationships": {r["kind"]: r["count"] for r in relations},
            "invariants": "passed",
            "sources": len(snapshot.sources),
            "dataset_version": snapshot.version,
            "content_hash": manifests[0]["hash"],
        }

    async def profile(self) -> list[dict[str, object]]:
        if self.adapter.driver is None:
            raise ApplicationError()
        operations: dict[str, tuple[str, dict[str, object]]] = {
            "list_roles": (
                "MATCH (n:KnowledgeEntity:Role) RETURN n.id ORDER BY n.name,n.id LIMIT $limit",
                {"limit": 50},
            ),
            "role_skills": (
                "MATCH (n:KnowledgeEntity {id:$id})-[r:REQUIRES_SKILL]->(s:Skill) "
                "RETURN s.id,r.id ORDER BY s.name,s.id LIMIT $limit",
                {"id": "role_backend_developer", "limit": 50},
            ),
            "skill_resources": (
                "MATCH (n:KnowledgeEntity {id:$id})<-[r:TEACHES_SKILL]-(s:Resource) "
                "RETURN s.id,r.id ORDER BY s.name,s.id LIMIT $limit",
                {"id": "skill_python", "limit": 50},
            ),
            "provenance": (
                "MATCH ()-[r:REQUIRES_SKILL]->() WHERE r.id=$id RETURN r.payload",
                {"id": assertion_id("role_backend_developer", "REQUIRES_SKILL", "skill_python")},
            ),
        }
        plans: list[dict[str, object]] = []
        async with self.adapter.driver.session(
            database=self.adapter.settings.neo4j_database
        ) as session:
            for name, (query, parameters) in operations.items():
                result = await session.run("PROFILE " + query, parameters)
                await result.data()
                summary = await result.consume()

                def operators(plan: Any) -> list[str]:
                    return [
                        plan["operatorType"],
                        *[op for child in plan.get("children", []) for op in operators(child)],
                    ]

                plans.append(
                    {
                        "operation": name,
                        "operators": operators(summary.profile),
                        "server_available_ms": summary.result_available_after,
                        "server_consumed_ms": summary.result_consumed_after,
                    }
                )
        return plans
