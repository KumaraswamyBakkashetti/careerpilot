import copy
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.errors import ApplicationError
from app.main import create_app
from app.modules.knowledge.dataset import dataset_hash, load_dataset
from app.modules.knowledge.models import (
    CompanyContext,
    Dataset,
    Entity,
    EntityPage,
    GraphEvidence,
    RelationsPage,
    assertion_id,
    normalize_alias,
)
from app.modules.knowledge.service import KnowledgeService
from tests.conftest import Probe


def raw_seed() -> dict[str, object]:
    return cast(dict[str, object], load_dataset().model_dump(mode="json"))


def test_canonical_seed_counts_and_hash_are_deterministic() -> None:
    dataset = load_dataset()
    assert dataset.version == "careerpilot-knowledge-v1"
    assert len(dataset.entities) == 36
    assert len(dataset.assertions) == 67
    assert len(dataset.sources) == 6
    assert dataset_hash(dataset) == dataset_hash(
        dataset.model_copy(update={"entities": list(reversed(dataset.entities))})
    )


def test_alias_and_assertion_identity_are_stable() -> None:
    assert normalize_alias("  PYTHON\u3000 3 ") == "python 3"
    assert assertion_id("role_backend_developer", "REQUIRES_SKILL", "skill_python") == (
        "assertion_77f01313c83d076670037afebc6c0f2c"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d["entities"].append(copy.deepcopy(d["entities"][0])),
        lambda d: d["assertions"][0].update(target_id="skill_missing"),
        lambda d: d["assertions"][0].update(importance=None),
        lambda d: d["assertions"][0].update(provenance=[]),
        lambda d: d["assertions"][0].update(type="TEACHES_SKILL"),
        lambda d: d["sources"][0].update(uri="http://unsafe.example"),
    ],
)
def test_invalid_seed_shapes_are_rejected(mutation: object) -> None:
    values = raw_seed()
    cast(object, mutation)(values)  # type: ignore[operator]
    with pytest.raises(ValidationError):
        Dataset.model_validate(values)


def test_source_snapshot_tampering_is_rejected() -> None:
    original = load_dataset()
    seed = Path(__file__).parents[1] / "knowledge_data"
    target = Path(__file__).parents[2] / "artifacts" / "phase2" / "tamper-seed"
    target.mkdir(parents=True, exist_ok=True)
    (target / "sources").mkdir(exist_ok=True)
    (target / "seed.json").write_text(
        (seed / "seed.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    for source in original.sources:
        (target / source.snapshot_path).write_bytes((seed / source.snapshot_path).read_bytes())
    (target / original.sources[0].snapshot_path).write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        load_dataset(target / "seed.json")


class FakeRepository:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def list_entities(self, kind: str, query: str, limit: int, offset: int) -> EntityPage:
        if self.fail:
            raise ApplicationError()
        roles = [
            e
            for e in load_dataset().entities
            if e.kind == kind and query.casefold() in e.name.casefold()
        ]
        return EntityPage(items=roles[offset : offset + limit], limit=limit, offset=offset)

    async def entity(self, identifier: str, kind: str) -> Entity | None:
        return next(
            (e for e in load_dataset().entities if e.id == identifier and e.kind == kind), None
        )

    async def related(self, *args: object, **kwargs: object) -> RelationsPage | None:
        return None

    async def evidence(self, identifier: str) -> GraphEvidence | None:
        return None

    async def company_context(self, identifier: str) -> CompanyContext | None:
        return None


def client_with(repository: FakeRepository) -> TestClient:
    settings = __import__("app.core.config", fromlist=["Settings"]).Settings(_env_file=None)
    probes = {"mongodb": Probe(), "neo4j": Probe()}
    return TestClient(create_app(settings, probes, cast(object, repository)))


def test_knowledge_api_list_detail_validation_and_404() -> None:
    with client_with(FakeRepository()) as client:
        response = client.get("/api/v1/knowledge/roles?q=backend")
        assert response.status_code == 200
        assert [item["id"] for item in response.json()["items"]] == ["role_backend_developer"]
        assert client.get("/api/v1/knowledge/roles/role_backend_developer").status_code == 200
        missing = client.get(
            "/api/v1/knowledge/roles/role_missing", headers={"X-Request-ID": "kg-404"}
        )
        assert missing.status_code == 404
        assert missing.json()["error"] == {
            "code": "KNOWLEDGE_NOT_FOUND",
            "message": "The requested knowledge entity does not exist.",
            "request_id": "kg-404",
        }
        assert client.get("/api/v1/knowledge/roles?limit=101").status_code == 422
        assert client.get("/api/v1/knowledge/roles/BAD-ID").status_code == 422


def test_knowledge_dependency_error_is_sanitized() -> None:
    with client_with(FakeRepository(fail=True)) as client:
        response = client.get("/api/v1/knowledge/roles", headers={"X-Request-ID": "kg-down"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
        assert response.json()["error"]["request_id"] == "kg-down"


@pytest.mark.asyncio
async def test_service_translates_missing_repository_values() -> None:
    service = KnowledgeService(FakeRepository())  # type: ignore[arg-type]
    with pytest.raises(ApplicationError) as raised:
        await service.related("role_missing", "Role", "REQUIRES_SKILL")
    assert raised.value.code == "KNOWLEDGE_NOT_FOUND"
