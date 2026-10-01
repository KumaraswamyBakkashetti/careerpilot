from datetime import UTC, datetime
from typing import Any, cast

from pymongo import ASCENDING, DESCENDING, IndexModel, ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.errors import ApplicationError
from app.infrastructure.mongodb import MongoDBAdapter
from app.modules.student.models import (
    GapAnalysisRun,
    ProcessingRun,
    ResumeRecord,
    SkillEvidence,
    StudentProfile,
)


class MongoStudentRepository:
    def __init__(self, adapter: MongoDBAdapter) -> None:
        self.adapter = adapter

    def database(self) -> Any:
        if self.adapter.client is None:
            raise ApplicationError()
        return self.adapter.client[self.adapter.settings.mongodb_database]

    async def initialize(self) -> None:
        database = self.database()
        try:
            await database.student_accounts.create_indexes(
                [IndexModel("student_id", unique=True), IndexModel("email", unique=True)]
            )
            await database.student_profiles.create_index("student_id", unique=True)
            await database.resumes.create_indexes(
                [
                    IndexModel("resume_id", unique=True),
                    IndexModel(
                        [("student_id", ASCENDING), ("content_hash", ASCENDING)], unique=True
                    ),
                    IndexModel([("student_id", ASCENDING), ("version", DESCENDING)], unique=True),
                    IndexModel([("student_id", ASCENDING), ("active", ASCENDING)]),
                ]
            )
            await database.resume_processing_runs.create_indexes(
                [IndexModel("processing_id", unique=True), IndexModel("resume_id", unique=True)]
            )
            await database.skill_evidence.create_indexes(
                [
                    IndexModel("evidence_id", unique=True),
                    IndexModel([("student_id", ASCENDING), ("skill_id", ASCENDING)]),
                    IndexModel([("student_id", ASCENDING), ("resume_id", ASCENDING)]),
                ]
            )
            await database.gap_analysis_runs.create_indexes(
                [
                    IndexModel("run_id", unique=True),
                    IndexModel([("student_id", ASCENDING), ("created_at", DESCENDING)]),
                ]
            )
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def create_account(
        self, student_id: str, email: str, password_hash: str, profile: StudentProfile
    ) -> None:
        database = self.database()
        try:
            # Standalone MongoDB has no multi-document transactions; compensate account insert.
            await database.student_accounts.insert_one(
                {"student_id": student_id, "email": email, "password_hash": password_hash}
            )
            try:
                await database.student_profiles.insert_one(profile.model_dump(mode="python"))
            except Exception:
                await database.student_accounts.delete_one({"student_id": student_id})
                raise
        except DuplicateKeyError as exc:
            raise ApplicationError("ACCOUNT_EXISTS") from exc
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def account_by_email(self, email: str) -> dict[str, object] | None:
        try:
            value = await self.database().student_accounts.find_one({"email": email}, {"_id": 0})
            return cast(dict[str, object] | None, value)
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def profile(self, student_id: str) -> StudentProfile | None:
        try:
            value = await self.database().student_profiles.find_one(
                {"student_id": student_id}, {"_id": 0, "resume_sequence": 0}
            )
            return StudentProfile.model_validate(value) if value else None
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def update_profile(
        self, student_id: str, display_name: str | None, target_role_id: str | None
    ) -> StudentProfile | None:
        changes: dict[str, object] = {"updated_at": datetime.now(UTC)}
        if display_name is not None:
            changes["display_name"] = display_name
        if target_role_id is not None:
            changes["target_role_id"] = target_role_id
        try:
            value = await self.database().student_profiles.find_one_and_update(
                {"student_id": student_id},
                {"$set": changes, "$inc": {"version": 1}},
                projection={"_id": 0, "resume_sequence": 0},
                return_document=ReturnDocument.AFTER,
            )
            return StudentProfile.model_validate(value) if value else None
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def next_resume_version(self, student_id: str) -> int:
        try:
            value = await self.database().student_profiles.find_one_and_update(
                {"student_id": student_id},
                {"$inc": {"resume_sequence": 1}},
                projection={"resume_sequence": 1},
                return_document=ReturnDocument.AFTER,
            )
            if not value:
                raise ApplicationError("PROFILE_NOT_FOUND")
            return int(value["resume_sequence"])
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def resume_by_hash(self, student_id: str, content_hash: str) -> ResumeRecord | None:
        try:
            value = await self.database().resumes.find_one(
                {
                    "student_id": student_id,
                    "content_hash": content_hash,
                    "status": {"$ne": "DELETED"},
                },
                {"_id": 0},
            )
            return ResumeRecord.model_validate(value) if value else None
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def create_resume(self, resume: ResumeRecord) -> None:
        try:
            await self.database().resumes.insert_one(resume.model_dump(mode="python"))
        except DuplicateKeyError as exc:
            raise ApplicationError("DUPLICATE_RESUME") from exc
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def update_resume_status(self, student_id: str, resume_id: str, status: str) -> None:
        try:
            result = await self.database().resumes.update_one(
                {"student_id": student_id, "resume_id": resume_id},
                {"$set": {"status": status, "updated_at": datetime.now(UTC)}},
            )
            if not result.matched_count:
                raise ApplicationError("RESUME_NOT_FOUND")
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def activate_resume(self, student_id: str, resume_id: str) -> None:
        try:
            await self.database().resumes.update_many(
                {"student_id": student_id, "resume_id": {"$ne": resume_id}, "active": True},
                {"$set": {"active": False}},
            )
            await self.database().resumes.update_one(
                {"student_id": student_id, "resume_id": resume_id}, {"$set": {"active": True}}
            )
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def resumes(self, student_id: str, limit: int) -> list[ResumeRecord]:
        try:
            cursor = (
                self.database()
                .resumes.find({"student_id": student_id, "status": {"$ne": "DELETED"}}, {"_id": 0})
                .sort("version", DESCENDING)
                .limit(limit)
            )
            return [ResumeRecord.model_validate(value) async for value in cursor]
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def resume(self, student_id: str, resume_id: str) -> ResumeRecord | None:
        try:
            value = await self.database().resumes.find_one(
                {"student_id": student_id, "resume_id": resume_id, "status": {"$ne": "DELETED"}},
                {"_id": 0},
            )
            return ResumeRecord.model_validate(value) if value else None
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def save_processing(self, run: ProcessingRun) -> None:
        try:
            await self.database().resume_processing_runs.replace_one(
                {"processing_id": run.processing_id}, run.model_dump(mode="python"), upsert=True
            )
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def save_evidence(self, values: list[SkillEvidence]) -> None:
        try:
            for value in values:
                await self.database().skill_evidence.update_one(
                    {"evidence_id": value.evidence_id},
                    {"$setOnInsert": value.model_dump(mode="python")},
                    upsert=True,
                )
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def evidence(self, student_id: str, resume_id: str | None = None) -> list[SkillEvidence]:
        query: dict[str, object] = {"student_id": student_id}
        if resume_id is not None:
            query["resume_id"] = resume_id
        try:
            cursor = (
                self.database()
                .skill_evidence.find(query, {"_id": 0})
                .sort([("created_at", ASCENDING), ("evidence_id", ASCENDING)])
            )
            return [SkillEvidence.model_validate(value) async for value in cursor]
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def evidence_item(self, student_id: str, evidence_id: str) -> SkillEvidence | None:
        try:
            value = await self.database().skill_evidence.find_one(
                {"student_id": student_id, "evidence_id": evidence_id}, {"_id": 0}
            )
            return SkillEvidence.model_validate(value) if value else None
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def decide_evidence(
        self,
        student_id: str,
        evidence_id: str,
        status: str,
        skill_id: str | None,
        skill_name: str | None,
    ) -> SkillEvidence | None:
        changes: dict[str, object] = {
            "verification_status": status,
            "updated_at": datetime.now(UTC),
        }
        if skill_id is not None:
            changes.update(
                {"skill_id": skill_id, "skill_name": skill_name, "normalization_status": "EXACT"}
            )
        try:
            value = await self.database().skill_evidence.find_one_and_update(
                {"student_id": student_id, "evidence_id": evidence_id},
                {"$set": changes},
                projection={"_id": 0},
                return_document=ReturnDocument.AFTER,
            )
            return SkillEvidence.model_validate(value) if value else None
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def save_gap(self, run: GapAnalysisRun) -> None:
        try:
            await self.database().gap_analysis_runs.insert_one(run.model_dump(mode="python"))
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def gap(self, student_id: str, run_id: str) -> GapAnalysisRun | None:
        try:
            value = await self.database().gap_analysis_runs.find_one(
                {"student_id": student_id, "run_id": run_id}, {"_id": 0}
            )
            return GapAnalysisRun.model_validate(value) if value else None
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def delete_resume_records(self, student_id: str, resume_id: str) -> bool:
        try:
            result = await self.database().resumes.update_one(
                {"student_id": student_id, "resume_id": resume_id, "status": {"$ne": "DELETED"}},
                {"$set": {"status": "DELETED", "active": False, "updated_at": datetime.now(UTC)}},
            )
            if not result.matched_count:
                return False
            await self.database().resume_processing_runs.delete_many(
                {"student_id": student_id, "resume_id": resume_id}
            )
            await self.database().skill_evidence.delete_many(
                {"student_id": student_id, "resume_id": resume_id}
            )
            return True
        except PyMongoError as exc:
            raise ApplicationError() from exc
