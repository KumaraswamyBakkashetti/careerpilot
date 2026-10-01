import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import ApplicationError
from app.core.logging import JsonFormatter, request_id_context
from app.main import create_app
from tests.conftest import Probe


def test_live_and_ready(client: TestClient, probes: dict[str, Probe]) -> None:
    assert client.get("/health/live").json() == {"status": "alive"}
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "dependencies": {"mongodb": "up", "neo4j": "up"}}
    assert all(probe.pings == 2 for probe in probes.values())


@pytest.mark.parametrize("failed", [("mongodb",), ("neo4j",), ("mongodb", "neo4j")])
def test_dependency_outages(
    client: TestClient, probes: dict[str, Probe], failed: tuple[str, ...]
) -> None:
    for name in failed:
        probes[name].available = False
    assert client.get("/health/live").status_code == 200
    response = client.get("/health/ready", headers={"X-Request-ID": "outage-check"})
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["dependencies"] == {name: "down" if name in failed else "up" for name in probes}
    assert body["error"]["request_id"] == response.headers["X-Request-ID"] == "outage-check"
    assert "secret-password" not in response.text
    for name in failed:
        probes[name].available = True
    assert client.get("/health/ready").status_code == 200


@pytest.mark.parametrize("value", ["valid_ID-123", "", "a" * 65, "bad value", "bad\nvalue"])
def test_request_id_policy(client: TestClient, value: str) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": value})
    returned = response.headers["X-Request-ID"]
    if value == "valid_ID-123":
        assert returned == value
    else:
        assert len(returned) == 32
        assert returned.isalnum()


def test_request_context_concurrency_and_reset(client: TestClient) -> None:
    def call(index: int) -> str:
        return client.get("/health/live", headers={"X-Request-ID": f"req-{index}"}).headers[
            "X-Request-ID"
        ]

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert list(executor.map(call, range(8))) == [f"req-{index}" for index in range(8)]
    assert request_id_context.get() is None


def test_not_found_and_method_contract(client: TestClient) -> None:
    response = client.get("/missing?secret=private")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
    response = client.post("/health/live")
    assert response.status_code == 405
    assert "GET" in response.headers["Allow"]


def add_test_routes(app: FastAPI) -> None:
    @app.get("/test-validation")
    async def validate(count: int) -> dict[str, int]:
        return {"count": count}

    @app.get("/test-crash")
    async def crash() -> None:
        raise RuntimeError("secret-password-do-not-expose")

    @app.get("/test-dependency")
    async def unavailable() -> None:
        raise ApplicationError()


def test_central_errors(settings: Settings, probes: dict[str, Probe]) -> None:
    app = create_app(settings, dict(probes))
    add_test_routes(app)
    with TestClient(app) as client:
        for path, status, code in [
            ("/test-validation?count=private-secret", 422, "VALIDATION_ERROR"),
            ("/test-crash", 500, "INTERNAL_ERROR"),
            ("/test-dependency", 503, "DEPENDENCY_UNAVAILABLE"),
        ]:
            response = client.get(path, headers={"Origin": "http://localhost:5173"})
            assert response.status_code == status
            assert response.json()["error"]["code"] == code
            assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
            assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
            assert "secret" not in response.text


def test_cors_and_security_headers(client: TestClient) -> None:
    response = client.options(
        "/health/ready",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Request-ID",
        },
    )
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert "Access-Control-Allow-Credentials" not in response.headers
    assert response.headers["X-Request-ID"]
    response = client.get("/health/live", headers={"Origin": "https://untrusted.test"})
    assert "Access-Control-Allow-Origin" not in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"


def test_openapi_and_versioned_api(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    assert spec["info"]["title"] == "CareerPilot"
    assert "503" in spec["paths"]["/health/ready"]["get"]["responses"]
    assert client.get("/docs").status_code == 200
    assert client.get("/api/v1/system").json()["phase"] == 1
    assert client.get("/system").status_code == 404


def test_json_logging_allowlist() -> None:
    record = logging.LogRecord(
        "careerpilot.requests", logging.INFO, "", 0, "request_completed", (), None
    )
    record.authorization = "private-token"
    record.duration_ms = 4.2
    token = request_id_context.set("logging-test")
    try:
        output = JsonFormatter().format(record)
    finally:
        request_id_context.reset(token)
    assert "private-token" not in output
    assert json.loads(output)["request_id"] == "logging-test"
    assert json.loads(output)["duration_ms"] == 4.2


def test_bounded_health_timeout(settings: Settings, probes: dict[str, Probe]) -> None:
    class SlowProbe(Probe):
        async def ping(self) -> None:
            await asyncio.sleep(10)

    probes["neo4j"] = SlowProbe()
    with TestClient(create_app(settings, dict(probes))) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["dependencies"] == {"mongodb": "up", "neo4j": "down"}
