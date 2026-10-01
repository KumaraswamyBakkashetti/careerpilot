import hashlib
import unicodedata
from datetime import datetime
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{2,79}$")]
Kind = Literal["Skill", "Role", "Company", "CompanyRole", "Resource", "InterviewTopic"]
RelationType = Literal[
    "OFFERS_ROLE", "BASED_ON", "REQUIRES_SKILL", "TEACHES_SKILL", "COVERS_TOPIC", "ASSESSES_SKILL"
]
Importance = Literal["CORE", "EXPECTED", "OPTIONAL", "UNSPECIFIED"]
ENDPOINTS: dict[str, set[tuple[str, str]]] = {
    "OFFERS_ROLE": {("Company", "CompanyRole")},
    "BASED_ON": {("CompanyRole", "Role")},
    "REQUIRES_SKILL": {("Role", "Skill"), ("CompanyRole", "Skill")},
    "TEACHES_SKILL": {("Resource", "Skill")},
    "COVERS_TOPIC": {("Resource", "InterviewTopic")},
    "ASSESSES_SKILL": {("InterviewTopic", "Skill")},
}
PREFIXES = {
    "Skill": "skill_",
    "Role": "role_",
    "Company": "company_",
    "CompanyRole": "companyrole_",
    "Resource": "resource_",
    "InterviewTopic": "topic_",
}


def normalize_alias(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def assertion_id(source: str, relation: str, target: str) -> str:
    digest = hashlib.sha256(f"{source}|{relation}|{target}".encode()).hexdigest()[:32]
    return f"assertion_{digest}"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Entity(StrictModel):
    id: Identifier
    kind: Kind
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=10, max_length=1000)
    aliases: list[str] = Field(default_factory=list, max_length=30)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    url: HttpUrl | None = None
    content_ref: Identifier | None = None
    source_ids: list[Identifier] = Field(min_length=1, max_length=20)
    synthetic: bool = False

    @model_validator(mode="after")
    def semantics(self) -> Self:
        if not self.id.startswith(PREFIXES[self.kind]):
            raise ValueError("Identifier prefix does not match entity kind")
        if self.kind == "Resource":
            if self.url is None or self.content_ref is None:
                raise ValueError("Resource requires URL and stable content reference")
            if self.url.scheme != "https":
                raise ValueError("Resources require HTTPS")
        elif self.url is not None or self.content_ref is not None:
            raise ValueError("Only Resource supports content linkage")
        if self.kind != "Skill" and (self.aliases or self.category is not None):
            raise ValueError("Aliases and category belong only to skills")
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("Duplicate entity source references")
        aliases: dict[str, str] = {}
        for alias in self.aliases:
            normalized = normalize_alias(alias)
            if not normalized or len(alias) > 120:
                raise ValueError("Invalid skill alias")
            if normalized != normalize_alias(self.name):
                aliases.setdefault(normalized, alias.strip())
        self.aliases = list(aliases.values())
        return self


class Source(StrictModel):
    id: Identifier
    source_type: Literal["CURATED_DATASET", "DOCUMENTATION"]
    title: str = Field(min_length=1, max_length=160)
    uri: str = Field(min_length=1, max_length=500)
    publisher: str = Field(min_length=1, max_length=120)
    collected_at: datetime
    published_at: datetime | None = None
    snapshot_path: str = Field(pattern=r"^sources/[a-z0-9_-]+\.md$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    synthetic: bool = False

    @model_validator(mode="after")
    def semantics(self) -> Self:
        parsed = urlsplit(self.uri)
        if not self.id.startswith("source_"):
            raise ValueError("Source ID requires source prefix")
        if self.source_type == "DOCUMENTATION":
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
            ):
                raise ValueError("Documentation sources require safe HTTPS URLs")
        elif not self.uri.startswith("urn:careerpilot:"):
            raise ValueError("Curated sources require a CareerPilot URN")
        if self.published_at and self.published_at > self.collected_at:
            raise ValueError("Publication cannot follow collection")
        return self

    @field_validator("collected_at", "published_at")
    @classmethod
    def timezone_required(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Source timestamps require timezone")
        return value


class Citation(StrictModel):
    source_id: Identifier
    evidence: str = Field(min_length=10, max_length=600)
    locator: str = Field(min_length=1, max_length=200)
    method: Literal["manual_curated", "source_derived", "synthetic"]


class Assertion(StrictModel):
    id: Identifier
    source_id: Identifier
    target_id: Identifier
    type: RelationType
    importance: Importance | None = None
    provenance: list[Citation] = Field(min_length=1, max_length=20)
    validated_at: datetime

    @model_validator(mode="after")
    def semantics(self) -> Self:
        if self.id != assertion_id(self.source_id, self.type, self.target_id):
            raise ValueError("Assertion identifier must match its logical triple")
        if (self.type == "REQUIRES_SKILL") != (self.importance is not None):
            raise ValueError(
                "Importance required only for REQUIRES_SKILL; use UNSPECIFIED if unknown"
            )
        if self.validated_at.tzinfo is None:
            raise ValueError("Validation timestamp requires timezone")
        if len({c.source_id for c in self.provenance}) != len(self.provenance):
            raise ValueError("Duplicate assertion source citations")
        return self


class Dataset(StrictModel):
    dataset_id: Literal["careerpilot_core"] = "careerpilot_core"
    version: str = Field(pattern=r"^careerpilot-knowledge-v[1-9][0-9]*$")
    validated_at: datetime
    sources: list[Source] = Field(min_length=1, max_length=500)
    entities: list[Entity] = Field(min_length=1, max_length=5000)
    assertions: list[Assertion] = Field(min_length=1, max_length=20000)

    @model_validator(mode="after")
    def invariants(self) -> Self:
        if self.validated_at.tzinfo is None:
            raise ValueError("Dataset validation timestamp requires timezone")
        for values in (self.sources, self.entities, self.assertions):
            if len({item.id for item in values}) != len(values):
                raise ValueError("Duplicate canonical IDs")
        sources = {s.id: s for s in self.sources}
        entities = {e.id: e for e in self.entities}
        aliases: dict[str, str] = {}
        names: set[tuple[str, str]] = set()
        for entity in self.entities:
            identity = (entity.kind, normalize_alias(entity.name))
            if identity in names:
                raise ValueError("Duplicate normalized entity name")
            names.add(identity)
            if any(source not in sources for source in entity.source_ids):
                raise ValueError("Unknown entity source")
            if entity.synthetic != any(sources[s].synthetic for s in entity.source_ids):
                raise ValueError("Entity synthetic marker must agree with sources")
            if entity.kind == "Skill":
                for name in [entity.name, *entity.aliases]:
                    alias = normalize_alias(name)
                    if alias in aliases and aliases[alias] != entity.id:
                        raise ValueError("Ambiguous canonical skill alias")
                    aliases[alias] = entity.id
        triples: set[tuple[str, str, str]] = set()
        for assertion in self.assertions:
            if assertion.source_id not in entities or assertion.target_id not in entities:
                raise ValueError("Dangling assertion endpoint")
            left, right = entities[assertion.source_id], entities[assertion.target_id]
            if (left.kind, right.kind) not in ENDPOINTS[assertion.type]:
                raise ValueError("Invalid relationship direction or endpoint kind")
            triple = (left.id, assertion.type, right.id)
            if triple in triples:
                raise ValueError("Duplicate logical relationship")
            triples.add(triple)
            for citation in assertion.provenance:
                if citation.source_id not in sources:
                    raise ValueError("Unknown provenance source")
                source = sources[citation.source_id]
                if source.collected_at > assertion.validated_at:
                    raise ValueError("Assertion cannot be validated before source collection")
                if (left.synthetic or right.synthetic or source.synthetic) != (
                    citation.method == "synthetic"
                ):
                    raise ValueError("Synthetic knowledge must be explicitly identified")
                if citation.method == "source_derived" and source.source_type != "DOCUMENTATION":
                    raise ValueError("Source-derived assertions require documentation")
            if assertion.validated_at > self.validated_at:
                raise ValueError("Assertion validation is newer than dataset validation")
        for entity in self.entities:
            if entity.kind == "CompanyRole":
                offers = [
                    a
                    for a in self.assertions
                    if a.type == "OFFERS_ROLE" and a.target_id == entity.id
                ]
                bases = [
                    a for a in self.assertions if a.type == "BASED_ON" and a.source_id == entity.id
                ]
                if len(offers) != 1 or len(bases) != 1:
                    raise ValueError("CompanyRole requires exactly one company and generic role")
        return self


class SupportedCitation(StrictModel):
    citation: Citation
    source: Source


class GraphEvidence(StrictModel):
    assertion: Assertion
    provenance: list[SupportedCitation]
    dataset_version: str
    path: list[str]


class RelatedEntity(StrictModel):
    entity: Entity
    evidence: GraphEvidence


class EntityPage(StrictModel):
    items: list[Entity]
    limit: int
    offset: int


class RelationsPage(StrictModel):
    entity: Entity
    items: list[RelatedEntity]
    limit: int
    offset: int


class CompanyContext(StrictModel):
    company_role: Entity
    company: RelatedEntity
    generic_role: RelatedEntity
