import pytest

from tests.test_integration import isolated_settings


@pytest.mark.parametrize(
    "variable,uri",
    [
        ("TEST_MONGODB_URI", "mongodb://production.example:27617"),
        ("TEST_MONGODB_URI", "mongodb://localhost:27017"),
        ("TEST_NEO4J_URI", "bolt://production.example:7767"),
        ("TEST_NEO4J_URI", "bolt://localhost:7687"),
    ],
)
def test_integration_rejects_nonisolated_targets(
    monkeypatch: pytest.MonkeyPatch, variable: str, uri: str
) -> None:
    monkeypatch.setenv(variable, uri)
    with pytest.raises(ValueError, match="dedicated loopback"):
        isolated_settings()


def test_integration_requires_explicit_test_password(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in ("TEST_MONGODB_URI", "TEST_NEO4J_URI", "TEST_NEO4J_PASSWORD"):
        monkeypatch.delenv(variable, raising=False)
    with pytest.raises(ValueError, match="TEST_NEO4J_PASSWORD"):
        isolated_settings()


def test_integration_uses_test_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_NEO4J_PASSWORD", "test-only-password")
    settings = isolated_settings()
    assert settings.app_env == "test"
    assert settings.mongodb_database == "careerpilot_test"
    assert settings.neo4j_uri == "bolt://127.0.0.1:7767"
