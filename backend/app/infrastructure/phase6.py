from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.errors import ApplicationError
from app.infrastructure.mongodb import MongoDBAdapter
from app.modules.phase6.models import (
    CompanyPreparation,
    InterviewSession,
    OrchestrationRun,
    ReadinessSnapshot,
    SpecialistGenerationRun,
)


class MongoPhase6Repository:
    def __init__(self, adapter: MongoDBAdapter) -> None:
        self.adapter = adapter

    def database(self) -> Any:
        if self.adapter.client is None:
            raise ApplicationError()
        return self.adapter.client[self.adapter.settings.mongodb_database]

    async def initialize(self) -> None:
        try:
            await self.database().company_preparations.create_indexes(
                [
                    IndexModel("preparation_id", unique=True),
                    IndexModel(
                        [("student_id", ASCENDING), ("request_identity", ASCENDING)], unique=True
                    ),
                    IndexModel([("student_id", ASCENDING), ("created_at", DESCENDING)]),
                ]
            )
            await self.database().interview_sessions.create_indexes(
                [
                    IndexModel("session_id", unique=True),
                    IndexModel(
                        [("student_id", ASCENDING), ("request_identity", ASCENDING)], unique=True
                    ),
                    IndexModel([("student_id", ASCENDING), ("created_at", DESCENDING)]),
                ]
            )
            await self.database().readiness_snapshots.create_indexes(
                [
                    IndexModel("snapshot_id", unique=True),
                    IndexModel(
                        [("student_id", ASCENDING), ("request_identity", ASCENDING)], unique=True
                    ),
                    IndexModel([("student_id", ASCENDING), ("version", ASCENDING)], unique=True),
                ]
            )
            await self.database().orchestration_runs.create_indexes(
                [
                    IndexModel("run_id", unique=True),
                    IndexModel([("student_id", ASCENDING), ("created_at", DESCENDING)]),
                ]
            )
            await self.database().specialist_generation_runs.create_indexes(
                [
                    IndexModel("run_id", unique=True),
                    IndexModel([("student_id", ASCENDING), ("created_at", DESCENDING)]),
                ]
            )
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def _insert(self, collection: str, value: dict[str, object]) -> bool:
        try:
            await self.database()[collection].insert_one(value)
            return True
        except DuplicateKeyError:
            return False
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def save_preparation(self, value: CompanyPreparation, identity: str) -> bool:
        document = value.model_dump(mode="python")
        document["request_identity"] = identity
        return await self._insert("company_preparations", document)

    async def preparation_by_identity(
        self, student_id: str, identity: str
    ) -> CompanyPreparation | None:
        value = await self.database().company_preparations.find_one(
            {"student_id": student_id, "request_identity": identity},
            {"_id": 0, "request_identity": 0},
        )
        return CompanyPreparation.model_validate(value) if value else None

    async def preparation(self, student_id: str, identifier: str) -> CompanyPreparation | None:
        value = await self.database().company_preparations.find_one(
            {"student_id": student_id, "preparation_id": identifier},
            {"_id": 0, "request_identity": 0},
        )
        return CompanyPreparation.model_validate(value) if value else None

    async def save_session(self, value: InterviewSession, identity: str) -> bool:
        document = value.model_dump(mode="python")
        document["request_identity"] = identity
        return await self._insert("interview_sessions", document)

    async def session_by_identity(self, student_id: str, identity: str) -> InterviewSession | None:
        value = await self.database().interview_sessions.find_one(
            {"student_id": student_id, "request_identity": identity},
            {"_id": 0, "request_identity": 0},
        )
        return InterviewSession.model_validate(value) if value else None

    async def session(self, student_id: str, identifier: str) -> InterviewSession | None:
        value = await self.database().interview_sessions.find_one(
            {"student_id": student_id, "session_id": identifier}, {"_id": 0, "request_identity": 0}
        )
        return InterviewSession.model_validate(value) if value else None

    async def replace_session(self, value: InterviewSession) -> None:
        try:
            await self.database().interview_sessions.replace_one(
                {"student_id": value.student_id, "session_id": value.session_id},
                {
                    **value.model_dump(mode="python"),
                    "request_identity": (
                        await self.database().interview_sessions.find_one(
                            {"session_id": value.session_id}, {"request_identity": 1}
                        )
                        or {}
                    ).get("request_identity", value.session_id),
                },
            )
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def save_readiness(self, value: ReadinessSnapshot, identity: str) -> bool:
        document = value.model_dump(mode="python")
        document["request_identity"] = identity
        return await self._insert("readiness_snapshots", document)

    async def readiness_by_identity(
        self, student_id: str, identity: str
    ) -> ReadinessSnapshot | None:
        value = await self.database().readiness_snapshots.find_one(
            {"student_id": student_id, "request_identity": identity},
            {"_id": 0, "request_identity": 0},
        )
        return ReadinessSnapshot.model_validate(value) if value else None

    async def readiness(self, student_id: str, identifier: str) -> ReadinessSnapshot | None:
        value = await self.database().readiness_snapshots.find_one(
            {"student_id": student_id, "snapshot_id": identifier}, {"_id": 0, "request_identity": 0}
        )
        return ReadinessSnapshot.model_validate(value) if value else None

    async def latest_readiness(self, student_id: str) -> ReadinessSnapshot | None:
        value = await self.database().readiness_snapshots.find_one(
            {"student_id": student_id},
            {"_id": 0, "request_identity": 0},
            sort=[("version", DESCENDING)],
        )
        return ReadinessSnapshot.model_validate(value) if value else None

    async def next_readiness_version(self, student_id: str) -> int:
        latest = await self.latest_readiness(student_id)
        return latest.version + 1 if latest else 1

    async def sessions(self, student_id: str, limit: int = 100) -> list[InterviewSession]:
        cursor = (
            self.database()
            .interview_sessions.find({"student_id": student_id}, {"_id": 0, "request_identity": 0})
            .sort("created_at", DESCENDING)
            .limit(limit)
        )
        return [InterviewSession.model_validate(item) async for item in cursor]

    async def save_orchestration(self, value: OrchestrationRun) -> None:
        if not await self._insert("orchestration_runs", value.model_dump(mode="python")):
            raise ApplicationError()

    async def save_generation(self, value: SpecialistGenerationRun) -> None:
        if not await self._insert("specialist_generation_runs", value.model_dump(mode="python")):
            raise ApplicationError()

    async def orchestration(self, student_id: str, identifier: str) -> OrchestrationRun | None:
        value = await self.database().orchestration_runs.find_one(
            {"student_id": student_id, "run_id": identifier}, {"_id": 0}
        )
        return OrchestrationRun.model_validate(value) if value else None
