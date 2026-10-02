import hashlib
import json
import logging
from datetime import UTC, datetime
from time import perf_counter
from typing import Literal, cast
from uuid import uuid4

from app.core.config import Settings
from app.core.errors import ApplicationError, ErrorCode
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.student.auth import AuthService
from app.modules.student.extraction import (
    PARSER_VERSION,
    detect_mentions,
    extract_text,
    validate_document,
)
from app.modules.student.models import (
    EvidenceDecision,
    GapAnalysisRun,
    GapItem,
    LoginRequest,
    ProcessingRun,
    RegisterRequest,
    ResumeRecord,
    ResumeView,
    SkillEvidence,
    StudentProfile,
    TokenResponse,
)
from app.modules.student.repository import StudentRepository
from app.modules.student.storage import LocalResumeStorage

GAP_RULE_VERSION = "gap-rules-v1"


def private_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def stable_private_id(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode()).hexdigest()[:32]}"


class StudentService:
    def __init__(
        self,
        settings: Settings,
        repository: StudentRepository,
        knowledge: KnowledgeRepository,
        storage: LocalResumeStorage,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.knowledge = knowledge
        self.storage = storage
        self.auth = AuthService(settings, repository)

    async def initialize(self) -> None:
        await self.repository.initialize()
        await self.storage.initialize()

    async def register(self, request: RegisterRequest) -> TokenResponse:
        self.auth.available_secret()
        now = datetime.now(UTC)
        student_id = private_id("student")
        profile = StudentProfile(
            student_id=student_id,
            display_name=request.display_name,
            created_at=now,
            updated_at=now,
            version=1,
        )
        await self.repository.create_account(
            student_id, request.email, self.auth.hash_password(request.password), profile
        )
        return self.auth.token(student_id)

    async def login(self, request: LoginRequest) -> TokenResponse:
        self.auth.available_secret()
        account = await self.repository.account_by_email(request.email.casefold())
        if not account or not self.auth.verify_password(
            request.password, str(account["password_hash"])
        ):
            raise ApplicationError("INVALID_CREDENTIALS")
        return self.auth.token(str(account["student_id"]))

    async def profile(self, student_id: str) -> StudentProfile:
        value = await self.repository.profile(student_id)
        if value is None:
            raise ApplicationError("PROFILE_NOT_FOUND")
        return value

    async def update_profile(
        self, student_id: str, display_name: str | None, target_role_id: str | None
    ) -> StudentProfile:
        if target_role_id is not None:
            role = await self.knowledge.entity(target_role_id, "Role")
            if role is None:
                raise ApplicationError("TARGET_ROLE_NOT_FOUND")
        value = await self.repository.update_profile(student_id, display_name, target_role_id)
        if value is None:
            raise ApplicationError("PROFILE_NOT_FOUND")
        return value

    async def upload(
        self, student_id: str, filename: str, media_type: str, content: bytes
    ) -> ResumeView:
        try:
            safe_name, kind = validate_document(
                filename, media_type, content, self.settings.resume_max_bytes
            )
        except ValueError as exc:
            code = cast(
                ErrorCode,
                {
                    "EMPTY": "EMPTY_RESUME",
                    "TOO_LARGE": "RESUME_TOO_LARGE",
                    "UNSUPPORTED": "UNSUPPORTED_RESUME_TYPE",
                    "CORRUPT": "INVALID_RESUME",
                    "Unsafe filename": "INVALID_FILENAME",
                }.get(str(exc), "INVALID_RESUME"),
            )
            raise ApplicationError(code) from exc
        content_hash = hashlib.sha256(content).hexdigest()
        duplicate = await self.repository.resume_by_hash(student_id, content_hash)
        if duplicate is not None:
            return ResumeView.from_record(duplicate, duplicate=True)
        now = datetime.now(UTC)
        resume_id = private_id("resume")
        extension = "pdf" if kind == "pdf" else "docx"
        storage_key = f"{resume_id}.{extension}"
        version = await self.repository.next_resume_version(student_id)
        record = ResumeRecord(
            resume_id=resume_id,
            student_id=student_id,
            original_filename=safe_name,
            media_type=cast(
                Literal[
                    "application/pdf",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ],
                media_type,
            ),
            size=len(content),
            content_hash=content_hash,
            storage_key=storage_key,
            status="STORED",
            version=version,
            active=False,
            parser_version=PARSER_VERSION,
            uploaded_at=now,
            updated_at=now,
        )
        try:
            await self.storage.save(storage_key, content)
            await self.repository.create_resume(record)
        except Exception:
            await self.storage.delete(storage_key)
            raise
        await self.repository.activate_resume(student_id, resume_id)
        try:
            await self.process(record, content, kind)
        except ApplicationError:
            raise
        current = await self.repository.resume(student_id, resume_id)
        if current is None:
            raise ApplicationError("RESUME_NOT_FOUND")
        return ResumeView.from_record(current)

    async def process(self, record: ResumeRecord, content: bytes, kind: str) -> None:
        processing_id = stable_private_id("processing", f"{record.resume_id}|{PARSER_VERSION}")
        run = ProcessingRun(
            processing_id=processing_id,
            resume_id=record.resume_id,
            student_id=record.student_id,
            parser_version=PARSER_VERSION,
            stages=["STORED"],
            started_at=datetime.now(UTC),
        )

        async def stage(value: str) -> None:
            run.stages.append(value)  # type: ignore[arg-type]
            await self.repository.update_resume_status(record.student_id, record.resume_id, value)
            await self.repository.save_processing(run)

        start = perf_counter()
        await stage("EXTRACTING_TEXT")
        try:
            text = extract_text(
                content, kind, self.settings.resume_max_pages, self.settings.resume_max_text_chars
            )
        except ValueError as exc:
            run.failure_code = str(exc)
            run.completed_at = datetime.now(UTC)
            await stage("TEXT_EXTRACTION_FAILED")
            raise ApplicationError("RESUME_EXTRACTION_FAILED") from exc
        await stage("EXTRACTING_STRUCTURE")
        await stage("NORMALIZING_SKILLS")
        try:
            skills = await self.knowledge.list_entities("Skill", "", 100, 0)
            mentions = detect_mentions(text, skills.items)
        except ApplicationError:
            run.failure_code = "DEPENDENCY_UNAVAILABLE"
            run.completed_at = datetime.now(UTC)
            await stage("NORMALIZATION_FAILED")
            raise
        now = datetime.now(UTC)
        evidence = [
            SkillEvidence(
                evidence_id=stable_private_id(
                    "evidence",
                    f"{record.resume_id}|{PARSER_VERSION}|{item.position}|{item.raw_text}|{item.skill_id}",
                ),
                student_id=record.student_id,
                resume_id=record.resume_id,
                raw_text=item.raw_text,
                section=item.section,
                evidence_text=item.evidence_text,
                skill_id=item.skill_id,
                skill_name=item.skill_name,
                normalization_status=item.normalization_status,
                observed_at=record.uploaded_at,
                created_at=now,
                updated_at=now,
            )
            for item in mentions
        ]
        await self.repository.save_evidence(evidence)
        run.completed_at = datetime.now(UTC)
        await stage("AWAITING_CONFIRMATION" if evidence else "COMPLETED")
        logging.getLogger("careerpilot.student").info(
            "resume_processed",
            extra={
                "operation": "resume_process",
                "result_count": len(evidence),
                "duration_ms": round((perf_counter() - start) * 1000, 2),
            },
        )

    async def list_resumes(self, student_id: str, limit: int) -> list[ResumeView]:
        return [
            ResumeView.from_record(value)
            for value in await self.repository.resumes(student_id, limit)
        ]

    async def retry(self, student_id: str, resume_id: str) -> ResumeView:
        record = await self.repository.resume(student_id, resume_id)
        if record is None:
            raise ApplicationError("RESUME_NOT_FOUND")
        content = await self.storage.read(record.storage_key)
        try:
            _, kind = validate_document(
                record.original_filename,
                record.media_type,
                content,
                self.settings.resume_max_bytes,
            )
        except ValueError as exc:
            raise ApplicationError("INVALID_RESUME") from exc
        await self.process(record, content, kind)
        current = await self.repository.resume(student_id, resume_id)
        if current is None:
            raise ApplicationError("RESUME_NOT_FOUND")
        return ResumeView.from_record(current)

    async def evidence(self, student_id: str, resume_id: str | None) -> list[SkillEvidence]:
        if resume_id is not None and await self.repository.resume(student_id, resume_id) is None:
            raise ApplicationError("RESUME_NOT_FOUND")
        return await self.repository.evidence(student_id, resume_id)

    async def decide(
        self, student_id: str, evidence_id: str, decision: EvidenceDecision
    ) -> SkillEvidence:
        existing = await self.repository.evidence_item(student_id, evidence_id)
        if existing is None:
            raise ApplicationError("EVIDENCE_NOT_FOUND")
        skill_id = existing.skill_id
        skill_name = existing.skill_name
        if decision.action == "CONFIRM":
            skill_id = decision.corrected_skill_id or skill_id
            if skill_id is None:
                raise ApplicationError("INVALID_SKILL_MAPPING")
            canonical = await self.knowledge.entity(skill_id, "Skill")
            if canonical is None:
                raise ApplicationError("SKILL_NOT_FOUND")
            skill_name = canonical.name
        elif decision.corrected_skill_id is not None:
            raise ApplicationError("INVALID_SKILL_MAPPING")
        result = await self.repository.decide_evidence(
            student_id,
            evidence_id,
            "CONFIRMED" if decision.action == "CONFIRM" else "REJECTED",
            skill_id,
            skill_name,
        )
        if result is None:
            raise ApplicationError("EVIDENCE_NOT_FOUND")
        remaining = (
            await self.repository.evidence(student_id, result.resume_id)
            if result.resume_id is not None
            else []
        )
        if (
            result.resume_id
            and remaining
            and all(item.verification_status != "EXTRACTED" for item in remaining)
        ):
            await self.repository.update_resume_status(student_id, result.resume_id, "COMPLETED")
        return result

    async def analyze(self, student_id: str) -> GapAnalysisRun:
        profile = await self.profile(student_id)
        if profile.target_role_id is None:
            raise ApplicationError("TARGET_ROLE_NOT_FOUND")
        requirements = await self.knowledge.related(
            profile.target_role_id, "Role", "REQUIRES_SKILL", False, 100, 0
        )
        if requirements is None:
            raise ApplicationError("TARGET_ROLE_NOT_FOUND")
        evidence = await self.repository.evidence(student_id)
        by_skill: dict[str, list[SkillEvidence]] = {}
        for item in evidence:
            if item.skill_id and item.verification_status != "REJECTED":
                by_skill.setdefault(item.skill_id, []).append(item)
        snapshot = [
            (item.evidence_id, item.skill_id, item.verification_status, item.updated_at.isoformat())
            for item in evidence
        ]
        evidence_hash = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        items: list[GapItem] = []
        versions: set[str] = set()
        for requirement in requirements.items:
            versions.add(requirement.evidence.dataset_version)
            matching = by_skill.get(requirement.entity.id, [])
            confirmed = [item for item in matching if item.verification_status == "CONFIRMED"]
            if confirmed:
                status, reason, used = "SUPPORTED", "CONFIRMED_DIRECT_EVIDENCE", confirmed
            elif matching:
                status, reason, used = (
                    "PARTIALLY_SUPPORTED",
                    "UNCONFIRMED_DIRECT_EVIDENCE",
                    matching,
                )
            else:
                status, reason, used = "UNVERIFIED", "NO_DIRECT_EVIDENCE", []
            items.append(
                GapItem(
                    skill_id=requirement.entity.id,
                    skill_name=requirement.entity.name,
                    importance=requirement.evidence.assertion.importance or "UNSPECIFIED",
                    status=status,  # type: ignore[arg-type]
                    reason_code=reason,  # type: ignore[arg-type]
                    evidence_ids=[item.evidence_id for item in used],
                    graph_assertion_id=requirement.evidence.assertion.id,
                )
            )
        if len(versions) != 1:
            raise ApplicationError("KNOWLEDGE_INCONSISTENT")
        run = GapAnalysisRun(
            run_id=private_id("gap"),
            student_id=student_id,
            target_role_id=profile.target_role_id,
            profile_version=profile.version,
            evidence_snapshot_hash=evidence_hash,
            knowledge_dataset_version=versions.pop(),
            created_at=datetime.now(UTC),
            items=items,
        )
        await self.repository.save_gap(run)
        return run

    async def gap(self, student_id: str, run_id: str) -> GapAnalysisRun:
        value = await self.repository.gap(student_id, run_id)
        if value is None:
            raise ApplicationError("GAP_ANALYSIS_NOT_FOUND")
        return value

    async def delete_resume(self, student_id: str, resume_id: str) -> None:
        record = await self.repository.resume(student_id, resume_id)
        if record is None:
            raise ApplicationError("RESUME_NOT_FOUND")
        if not await self.repository.delete_resume_records(student_id, resume_id):
            raise ApplicationError("RESUME_NOT_FOUND")
        await self.storage.delete(record.storage_key)
