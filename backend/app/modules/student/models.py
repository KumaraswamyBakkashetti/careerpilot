import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PrivateId = Annotated[
    str, Field(pattern=r"^(student|resume|evidence|gap|processing)_[a-f0-9]{32}$")
]
CanonicalId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{2,79}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RegisterRequest(StrictModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("email")
    @classmethod
    def email_shape(cls, value: str) -> str:
        normalized = value.casefold()
        if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,63}", normalized):
            raise ValueError("Invalid email address")
        return normalized


class LoginRequest(StrictModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(StrictModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class StudentIdentity(StrictModel):
    student_id: PrivateId


class StudentProfile(StrictModel):
    student_id: PrivateId
    display_name: str
    target_role_id: CanonicalId | None = None
    created_at: datetime
    updated_at: datetime
    version: int = Field(ge=1)


class ProfileUpdate(StrictModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    target_role_id: CanonicalId | None = None


ResumeStatus = Literal[
    "STORED",
    "EXTRACTING_TEXT",
    "EXTRACTING_STRUCTURE",
    "NORMALIZING_SKILLS",
    "AWAITING_CONFIRMATION",
    "COMPLETED",
    "TEXT_EXTRACTION_FAILED",
    "NORMALIZATION_FAILED",
    "DELETED",
]


class ResumeRecord(StrictModel):
    resume_id: PrivateId
    student_id: PrivateId
    original_filename: str
    media_type: Literal[
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]
    size: int = Field(gt=0)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    storage_key: str
    status: ResumeStatus
    version: int = Field(ge=1)
    active: bool
    duplicate: bool = False
    parser_version: str
    uploaded_at: datetime
    updated_at: datetime


class ResumeView(StrictModel):
    resume_id: PrivateId
    original_filename: str
    media_type: str
    size: int
    content_hash: str
    status: ResumeStatus
    version: int
    active: bool
    duplicate: bool = False
    parser_version: str
    uploaded_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, value: ResumeRecord, duplicate: bool = False) -> "ResumeView":
        return cls(
            **value.model_dump(exclude={"student_id", "storage_key", "duplicate"}),
            duplicate=duplicate,
        )


class ProcessingRun(StrictModel):
    processing_id: PrivateId
    resume_id: PrivateId
    student_id: PrivateId
    parser_version: str
    stages: list[ResumeStatus]
    started_at: datetime
    completed_at: datetime | None = None
    failure_code: str | None = None


NormalizationStatus = Literal["EXACT", "ALIAS", "UNRESOLVED"]
VerificationStatus = Literal["EXTRACTED", "CONFIRMED", "REJECTED"]
Section = Literal["SKILLS", "PROJECTS", "EXPERIENCE", "EDUCATION", "CERTIFICATIONS", "OTHER"]


class SkillEvidence(StrictModel):
    evidence_id: PrivateId
    student_id: PrivateId
    resume_id: PrivateId
    raw_text: str = Field(min_length=1, max_length=120)
    section: Section
    evidence_text: str = Field(min_length=1, max_length=500)
    skill_id: CanonicalId | None = None
    skill_name: str | None = None
    normalization_status: NormalizationStatus
    extraction_method: Literal["DETERMINISTIC_ALIAS_V1"] = "DETERMINISTIC_ALIAS_V1"
    verification_status: VerificationStatus = "EXTRACTED"
    observed_at: datetime
    created_at: datetime
    updated_at: datetime


class EvidenceDecision(StrictModel):
    action: Literal["CONFIRM", "REJECT"]
    corrected_skill_id: CanonicalId | None = None


GapStatus = Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "UNVERIFIED"]


class GapItem(StrictModel):
    skill_id: CanonicalId
    skill_name: str
    importance: Literal["CORE", "EXPECTED", "OPTIONAL", "UNSPECIFIED"]
    status: GapStatus
    reason_code: Literal[
        "CONFIRMED_DIRECT_EVIDENCE", "UNCONFIRMED_DIRECT_EVIDENCE", "NO_DIRECT_EVIDENCE"
    ]
    evidence_ids: list[PrivateId]
    graph_assertion_id: CanonicalId


class GapAnalysisRun(StrictModel):
    run_id: PrivateId
    student_id: PrivateId
    target_role_id: CanonicalId
    profile_version: int
    evidence_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    knowledge_dataset_version: str
    rule_version: Literal["gap-rules-v1"] = "gap-rules-v1"
    created_at: datetime
    items: list[GapItem]
