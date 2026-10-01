from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


class Probe:
    """Boundary fake records lifecycle; API, middleware and health service remain real."""

    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.started = 0
        self.closed = 0
        self.pings = 0

    async def start(self) -> None:
        self.started += 1

    async def ping(self) -> None:
        self.pings += 1
        if not self.available:
            raise ConnectionError("secret-password-do-not-expose")

    async def close(self) -> None:
        self.closed += 1


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, app_env="test", dependency_timeout_seconds=0.1)


@pytest.fixture
def probes() -> dict[str, Probe]:
    return {"mongodb": Probe(), "neo4j": Probe()}


@pytest.fixture
def client(settings: Settings, probes: dict[str, Probe]) -> Iterator[TestClient]:
    with TestClient(create_app(settings, dict(probes))) as session:
        yield session
