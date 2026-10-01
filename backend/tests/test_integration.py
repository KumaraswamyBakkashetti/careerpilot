"""Read-only real connectivity tests, restricted to dedicated local test ports."""

import os
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.infrastructure.mongodb import MongoDBAdapter
from app.infrastructure.neo4j import Neo4jAdapter
from app.main import create_app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("CP_RUN_INTEGRATION") != "1",
        reason="Opt-in isolated databases required; see README",
    ),
]


def isolated_settings() -> Settings:
    mongo = os.environ.get("TEST_MONGODB_URI", "mongodb://127.0.0.1:27617")
    neo = os.environ.get("TEST_NEO4J_URI", "bolt://127.0.0.1:7767")
    for uri, port in ((mongo, 27617), (neo, 7767)):
        parsed = urlsplit(uri)
        if parsed.hostname not in {"localhost", "127.0.0.1"} or parsed.port != port:
            raise ValueError("Integration tests only allow dedicated loopback test ports")
    password = os.environ.get("TEST_NEO4J_PASSWORD", "")
    if not password:
        raise ValueError("TEST_NEO4J_PASSWORD is required for isolated integration services")
    return Settings(
        _env_file=None,
        app_env="test",
        mongodb_uri=SecretStr(mongo),
        mongodb_database="careerpilot_test",
        neo4j_uri=neo,
        neo4j_password=SecretStr(password),
        dependency_timeout_seconds=5,
    )


async def test_real_mongodb_connectivity() -> None:
    adapter = MongoDBAdapter(isolated_settings())
    try:
        await adapter.start()
        await adapter.ping()
    finally:
        await adapter.close()
    assert adapter.client is None


async def test_real_neo4j_connectivity() -> None:
    adapter = Neo4jAdapter(isolated_settings())
    try:
        await adapter.start()
        await adapter.ping()
    finally:
        await adapter.close()
    assert adapter.driver is None


def test_real_application_lifecycle_and_readiness() -> None:
    settings = isolated_settings()
    mongo, neo = MongoDBAdapter(settings), Neo4jAdapter(settings)
    with TestClient(create_app(settings, {"mongodb": mongo, "neo4j": neo})) as client:
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["dependencies"] == {"mongodb": "up", "neo4j": "up"}
    assert mongo.client is None
    assert neo.driver is None


@pytest.mark.parametrize(
    "overrides,failed",
    [
        ({"neo4j_password": SecretStr("intentionally-wrong-test-password")}, "neo4j"),
        ({"neo4j_database": "missing_careerpilot_test"}, "neo4j"),
        (
            {"mongodb_uri": SecretStr("mongodb://nonexistent_test_user:wrong@127.0.0.1:27617")},
            "mongodb",
        ),
    ],
)
def test_real_invalid_dependency_configuration(overrides: dict[str, object], failed: str) -> None:
    settings = isolated_settings().model_copy(update=overrides)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/live").status_code == 200
        response = client.get("/health/ready", headers={"X-Request-ID": "invalid-config-test"})
        assert response.status_code == 503
        assert response.json()["dependencies"][failed] == "down"
        assert response.json()["error"]["request_id"] == "invalid-config-test"
        assert "password" not in response.text
        assert "nonexistent_test_user" not in response.text
