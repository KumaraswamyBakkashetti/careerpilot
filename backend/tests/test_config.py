import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings


def test_development_defaults() -> None:
    config = Settings(_env_file=None)
    assert config.app_name == "CareerPilot"
    assert config.api_prefix == "/api/v1"
    assert not config.debug
    assert not config.neo4j_password.get_secret_value()


def test_environment_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CP_PORT", "8123")
    monkeypatch.setenv("CP_CORS_ORIGINS", '["https://careerpilot.example"]')
    assert Settings(_env_file=None).port == 8123
    assert Settings(_env_file=None).cors_origins == ["https://careerpilot.example"]


@pytest.mark.parametrize("origin", ["*", "https://site.test/", "file://site", "https://u:p@site"])
def test_reject_unsafe_cors(origin: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=[origin])


@pytest.mark.parametrize(
    "field,value",
    [
        ("mongodb_uri", "https://localhost"),
        ("neo4j_uri", "bolt://user:password@localhost"),
        ("neo4j_uri", "bolt+ssc://localhost"),
        ("mongodb_database", "wrong/name"),
        ("dependency_timeout_seconds", 0),
        ("port", 70000),
    ],
)
def test_reject_invalid_configuration(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_production_cannot_use_implicit_defaults() -> None:
    with pytest.raises(ValidationError, match="explicit"):
        Settings(_env_file=None, app_env="production")


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = dict(
        app_env="production",
        mongodb_uri="mongodb://db.internal:27017",
        mongodb_database="careerpilot",
        neo4j_uri="neo4j+s://graph.internal",
        neo4j_user="careerpilot",
        neo4j_password="test-only-password",
        cors_origins=["https://careerpilot.example"],
        jwt_secret="a" * 32,
        resume_storage_root="C:/private/careerpilot-resumes",
    )
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_explicit_production_configuration() -> None:
    assert production_settings().app_env == "production"


@pytest.mark.parametrize(
    "overrides",
    [
        {"debug": True},
        {"neo4j_password": ""},
        {"cors_origins": ["http://localhost:5173"]},
    ],
)
def test_production_security_policy(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        production_settings(**overrides)


def test_secret_representation() -> None:
    config = Settings(_env_file=None, neo4j_password=SecretStr("private-test-value"))
    assert "private-test-value" not in repr(config)
