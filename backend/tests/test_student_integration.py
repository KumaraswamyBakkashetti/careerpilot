"""Real MongoDB + Neo4j + PDF pipeline and server-side ownership verification."""

import asyncio
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.infrastructure.knowledge import GraphWriter
from app.infrastructure.mongodb import MongoDBAdapter
from app.infrastructure.neo4j import Neo4jAdapter
from app.main import create_app
from app.modules.knowledge.dataset import load_dataset
from tests.test_integration import isolated_settings
from tests.test_student import synthetic_docx, synthetic_pdf

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("CP_RUN_INTEGRATION") != "1",
        reason="Opt-in isolated databases required; see README",
    ),
]


def phase3_settings():
    return isolated_settings().model_copy(
        update={
            "jwt_secret": SecretStr("phase3-integration-secret-32-characters"),
            "resume_storage_root": Path(__file__).parents[2]
            / "artifacts/phase3/integration-resumes",
        }
    )


async def seed_graph() -> None:
    adapter = Neo4jAdapter(phase3_settings())
    try:
        await adapter.start()
        await adapter.ping()
        writer = GraphWriter(adapter)
        await writer.schema()
        await writer.ingest(load_dataset())
    finally:
        await adapter.close()


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client: TestClient, email: str, name: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "synthetic-test-password", "display_name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_real_private_resume_cross_store_workflow_and_ownership() -> None:
    asyncio.run(seed_graph())
    settings = phase3_settings()
    mongo, neo = MongoDBAdapter(settings), Neo4jAdapter(settings)
    unique = os.urandom(6).hex()
    with TestClient(create_app(settings, {"mongodb": mongo, "neo4j": neo})) as client:
        owner_token = register(client, f"owner-{unique}@example.test", "Synthetic Owner")
        other_token = register(client, f"other-{unique}@example.test", "Synthetic Other")
        owner = authorization(owner_token)
        other = authorization(other_token)

        assert client.get("/api/v1/student/profile").status_code == 401
        profile = client.get("/api/v1/student/profile", headers=owner)
        assert profile.status_code == 200 and profile.json()["display_name"] == "Synthetic Owner"

        malicious = [
            ("../escape.pdf", synthetic_pdf(), "application/pdf", 422),
            ("fake.pdf", b"not a pdf", "application/pdf", 415),
            ("empty.pdf", b"", "application/pdf", 422),
            ("wrong.pdf", synthetic_pdf(), "application/octet-stream", 415),
            ("broken.pdf", b"%PDF-broken", "application/pdf", 422),
            (
                "broken.docx",
                b"PK broken",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                422,
            ),
        ]
        for filename, content, media_type, status in malicious:
            response = client.post(
                "/api/v1/student/resumes",
                headers=owner,
                files={"file": (filename, content, media_type)},
            )
            assert response.status_code == status
            assert "traceback" not in response.text.casefold()
        oversized = client.post(
            "/api/v1/student/resumes",
            headers=owner,
            files={
                "file": (
                    "large.pdf",
                    b"%PDF-" + b"x" * settings.resume_max_bytes,
                    "application/pdf",
                )
            },
        )
        assert oversized.status_code == 413

        pdf = synthetic_pdf()
        upload = client.post(
            "/api/v1/student/resumes",
            headers=owner,
            files={"file": ("synthetic-resume.pdf", pdf, "application/pdf")},
        )
        assert upload.status_code == 200, upload.text
        resume = upload.json()
        assert resume["status"] == "AWAITING_CONFIRMATION"
        # The malformed-but-stored PDF remains as explicit failed version 1.
        assert resume["version"] == 2 and resume["active"] is True
        assert "storage" not in resume

        duplicate = client.post(
            "/api/v1/student/resumes",
            headers=owner,
            files={"file": ("renamed.pdf", pdf, "application/pdf")},
        )
        assert duplicate.status_code == 200
        assert duplicate.json()["resume_id"] == resume["resume_id"]
        assert duplicate.json()["duplicate"] is True

        evidence_response = client.get(
            f"/api/v1/student/resumes/{resume['resume_id']}/evidence", headers=owner
        )
        assert evidence_response.status_code == 200
        evidence = evidence_response.json()
        assert {item["skill_id"] for item in evidence if item["skill_id"]} >= {
            "skill_python",
            "skill_sql",
            "skill_rest",
        }
        unresolved = next(item for item in evidence if item["normalization_status"] == "UNRESOLVED")
        python = next(item for item in evidence if item["skill_id"] == "skill_python")

        # The same private identifier is enumeration-resistant for another student.
        assert (
            client.get(
                f"/api/v1/student/resumes/{resume['resume_id']}/evidence", headers=other
            ).status_code
            == 404
        )
        assert (
            client.put(
                f"/api/v1/student/evidence/{python['evidence_id']}",
                headers=other,
                json={"action": "REJECT"},
            ).status_code
            == 404
        )

        confirmed = client.put(
            f"/api/v1/student/evidence/{python['evidence_id']}",
            headers=owner,
            json={"action": "CONFIRM"},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["verification_status"] == "CONFIRMED"
        corrected = client.put(
            f"/api/v1/student/evidence/{unresolved['evidence_id']}",
            headers=owner,
            json={"action": "CONFIRM", "corrected_skill_id": "skill_javascript"},
        )
        assert corrected.status_code == 200
        assert corrected.json()["skill_id"] == "skill_javascript"

        invalid = client.put(
            f"/api/v1/student/evidence/{unresolved['evidence_id']}",
            headers=owner,
            json={"action": "CONFIRM", "corrected_skill_id": "skill_not_canonical"},
        )
        assert invalid.status_code == 404

        retry = client.post(f"/api/v1/student/resumes/{resume['resume_id']}/process", headers=owner)
        assert retry.status_code == 200
        repeated = client.get(
            f"/api/v1/student/resumes/{resume['resume_id']}/evidence", headers=owner
        ).json()
        assert len(repeated) == len(evidence)
        assert (
            next(item for item in repeated if item["evidence_id"] == python["evidence_id"])[
                "verification_status"
            ]
            == "CONFIRMED"
        )

        profile = client.put(
            "/api/v1/student/profile",
            headers=owner,
            json={"target_role_id": "role_backend_developer"},
        )
        assert profile.status_code == 200
        gap = client.post("/api/v1/student/gap-analyses", headers=owner)
        assert gap.status_code == 201, gap.text
        run = gap.json()
        statuses = {item["skill_id"]: item["status"] for item in run["items"]}
        assert statuses["skill_python"] == "SUPPORTED"
        assert statuses["skill_sql"] == "PARTIALLY_SUPPORTED"
        assert "UNVERIFIED" in statuses.values()
        assert run["knowledge_dataset_version"] == "careerpilot-knowledge-v1"
        assert (
            client.get(f"/api/v1/student/gap-analyses/{run['run_id']}", headers=other).status_code
            == 404
        )

        docx = client.post(
            "/api/v1/student/resumes",
            headers=owner,
            files={
                "file": (
                    "synthetic-v2.docx",
                    synthetic_docx(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert docx.status_code == 200
        assert docx.json()["version"] == resume["version"] + 1 and docx.json()["active"] is True
        listed = client.get("/api/v1/student/resumes", headers=owner).json()
        assert [item["version"] for item in listed] == [3, 2, 1]
        assert listed[1]["active"] is False

        deleted = client.delete(
            f"/api/v1/student/resumes/{docx.json()['resume_id']}", headers=owner
        )
        assert deleted.status_code == 204
        assert (
            client.get(
                f"/api/v1/student/resumes/{docx.json()['resume_id']}/evidence", headers=owner
            ).status_code
            == 404
        )

    assert mongo.client is None and neo.driver is None


async def test_real_mongodb_indexes_and_private_records() -> None:
    settings = phase3_settings()
    adapter = MongoDBAdapter(settings)
    try:
        await adapter.start()
        await adapter.ping()
        database = adapter.client[settings.mongodb_database]  # type: ignore[index]
        names = set(await database.list_collection_names())
        assert {"student_profiles", "resumes", "skill_evidence", "gap_analysis_runs"} <= names
        resume_indexes = await database.resumes.index_information()
        assert any(value.get("unique") for value in resume_indexes.values())
        assert await database.student_profiles.count_documents({}) >= 2
        assert await database.gap_analysis_runs.count_documents({}) >= 1
    finally:
        await adapter.close()
