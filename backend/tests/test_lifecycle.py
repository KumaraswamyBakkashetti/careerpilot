from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.conftest import Probe


def test_clients_initialized_once_and_closed(settings: Settings, probes: dict[str, Probe]) -> None:
    app = create_app(settings, dict(probes))
    with TestClient(app) as client:
        client.get("/health/ready")
        client.get("/health/ready")
        assert all(probe.started == 1 and probe.closed == 0 for probe in probes.values())
    assert all(probe.closed == 1 for probe in probes.values())


def test_start_failure_preserves_liveness_and_cleanup(settings: Settings) -> None:
    class FailedProbe(Probe):
        async def start(self) -> None:
            self.started += 1
            raise ConnectionError("private-credentials")

    failing = FailedProbe(available=False)
    other = Probe()
    with TestClient(create_app(settings, {"mongodb": failing, "neo4j": other})) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
    assert failing.closed == other.closed == 1


def test_one_close_failure_does_not_prevent_other_cleanup(settings: Settings) -> None:
    class CloseFailure(Probe):
        async def close(self) -> None:
            self.closed += 1
            raise RuntimeError("private-credentials")

    first, second = Probe(), CloseFailure()
    with TestClient(create_app(settings, {"mongodb": first, "neo4j": second})):
        pass
    assert first.closed == second.closed == 1
