import re
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        env_prefix="CP_",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_name: Literal["CareerPilot"] = "CareerPilot"
    app_env: Literal["development", "test", "production"] = "development"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    api_prefix: Literal["/api/v1"] = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    mongodb_uri: SecretStr = SecretStr("mongodb://localhost:27017")
    mongodb_database: str = "careerpilot_dev"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = Field(default="neo4j", min_length=1, max_length=128)
    neo4j_password: SecretStr = SecretStr("")
    neo4j_database: str = "neo4j"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    dependency_timeout_seconds: float = Field(default=3, ge=0.1, le=30)
    jwt_secret: SecretStr = SecretStr("")
    jwt_ttl_minutes: int = Field(default=60, ge=5, le=1440)
    resume_max_bytes: int = Field(default=5_242_880, ge=1024, le=20_971_520)
    resume_max_pages: int = Field(default=20, ge=1, le=100)
    resume_max_text_chars: int = Field(default=200_000, ge=1000, le=1_000_000)
    resume_storage_root: Path = Path(__file__).resolve().parents[3] / "uploads" / "resumes"
    retrieval_index_root: Path = Path(__file__).resolve().parents[3] / "indexes" / "retrieval"
    retrieval_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    retrieval_embedding_revision: str = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    retrieval_embedding_dimension: int = Field(default=384, ge=64, le=4096)
    retrieval_chunk_size: int = Field(default=420, ge=200, le=4000)
    retrieval_chunk_overlap: int = Field(default=40, ge=0, le=1000)
    retrieval_top_k: int = Field(default=3, ge=1, le=20)
    retrieval_max_top_k: int = Field(default=20, ge=1, le=100)
    llm_provider: Literal["groq"] = "groq"
    groq_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="GROQ_API_KEY")
    groq_model: str = "openai/gpt-oss-120b"
    groq_reasoning_effort: Literal["low", "medium", "high"] = "medium"
    groq_timeout_seconds: float = Field(default=45, ge=1, le=120)
    groq_max_retries: int = Field(default=1, ge=0, le=2)
    groq_base_url: str = "https://api.groq.com/openai/v1"

    @field_validator("cors_origins")
    @classmethod
    def explicit_origins(cls, values: list[str]) -> list[str]:
        for value in values:
            parsed = urlsplit(value)
            _ = parsed.port  # Invalid URL ports are configuration errors.
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
                or "*" in value
            ):
                raise ValueError("CORS origins must be explicit HTTP(S) origins without paths")
        return values

    @field_validator("mongodb_database", "neo4j_database")
    @classmethod
    def database_name(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,63}", value):
            raise ValueError(
                "Database name must contain only letters, digits, underscores or dashes"
            )
        return value

    @field_validator("mongodb_uri")
    @classmethod
    def mongo_scheme(cls, value: SecretStr) -> SecretStr:
        parsed = urlsplit(value.get_secret_value())
        if parsed.scheme not in {"mongodb", "mongodb+srv"} or not parsed.netloc:
            raise ValueError("MongoDB URI must use mongodb or mongodb+srv")
        return value

    @field_validator("neo4j_uri")
    @classmethod
    def neo4j_scheme(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"bolt", "bolt+s", "neo4j", "neo4j+s"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Neo4j URI must use an approved scheme without embedded credentials")
        return value

    @field_validator("groq_base_url")
    @classmethod
    def groq_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Groq base URL must be HTTPS without embedded credentials")
        return value.rstrip("/")

    @model_validator(mode="after")
    def production_policy(self) -> Self:
        if self.retrieval_chunk_overlap >= self.retrieval_chunk_size:
            raise ValueError("Retrieval chunk overlap must be smaller than chunk size")
        if self.retrieval_top_k > self.retrieval_max_top_k:
            raise ValueError("Retrieval top-k exceeds configured maximum")
        if self.app_env == "production":
            required = {
                "mongodb_uri",
                "mongodb_database",
                "neo4j_uri",
                "neo4j_user",
                "neo4j_password",
                "cors_origins",
                "jwt_secret",
                "resume_storage_root",
            }
            if not required.issubset(self.model_fields_set):
                raise ValueError("Production requires explicit database and CORS configuration")
            if not self.neo4j_password.get_secret_value() or self.debug:
                raise ValueError("Production requires a Neo4j password and debug disabled")
            if len(self.jwt_secret.get_secret_value()) < 32:
                raise ValueError("Production requires a JWT secret of at least 32 characters")
            if any(not origin.startswith("https://") for origin in self.cors_origins):
                raise ValueError("Production CORS origins must use HTTPS")
        return self
