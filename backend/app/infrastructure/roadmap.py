from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.errors import ApplicationError
from app.infrastructure.mongodb import MongoDBAdapter
from app.modules.roadmap.models import GenerationRun, Roadmap


class MongoRoadmapRepository:
    def __init__(self, adapter: MongoDBAdapter) -> None:
        self.adapter = adapter

    def database(self) -> Any:
        if self.adapter.client is None:
            raise ApplicationError()
        return self.adapter.client[self.adapter.settings.mongodb_database]

    async def initialize(self) -> None:
        try:
            await self.database().generation_runs.create_indexes(
                [
                    IndexModel("run_id", unique=True),
                    IndexModel(
                        [("student_id", ASCENDING), ("request_identity", ASCENDING)],
                        unique=True,
                    ),
                    IndexModel([("student_id", ASCENDING), ("created_at", DESCENDING)]),
                ]
            )
            await self.database().roadmaps.create_indexes(
                [
                    IndexModel("roadmap_id", unique=True),
                    IndexModel([("student_id", ASCENDING), ("version", ASCENDING)], unique=True),
                    IndexModel([("student_id", ASCENDING), ("generated_at", DESCENDING)]),
                ]
            )
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def save_run(self, run: GenerationRun) -> bool:
        try:
            await self.database().generation_runs.insert_one(run.model_dump(mode="python"))
            return True
        except DuplicateKeyError:
            # A concurrent identical request owns this identity. The caller can retrieve it.
            return False
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def replace_run(self, run: GenerationRun) -> None:
        try:
            await self.database().generation_runs.replace_one(
                {"run_id": run.run_id, "student_id": run.student_id},
                run.model_dump(mode="python"),
                upsert=False,
            )
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def save_roadmap(self, roadmap: Roadmap) -> None:
        try:
            await self.database().roadmaps.insert_one(roadmap.model_dump(mode="python"))
        except DuplicateKeyError as exc:
            raise ApplicationError() from exc
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def by_identity(self, student_id: str, identity: str) -> Roadmap | None:
        try:
            run = await self.database().generation_runs.find_one(
                {
                    "student_id": student_id,
                    "request_identity": identity,
                    "status": "COMPLETED",
                    "output_roadmap_id": {"$ne": None},
                },
                {"_id": 0},
            )
            if not run:
                return None
            return await self.get(student_id, str(run["output_roadmap_id"]))
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def get(self, student_id: str, roadmap_id: str) -> Roadmap | None:
        try:
            value = await self.database().roadmaps.find_one(
                {"student_id": student_id, "roadmap_id": roadmap_id}, {"_id": 0}
            )
            return Roadmap.model_validate(value) if value else None
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def list(self, student_id: str, limit: int) -> list[Roadmap]:
        try:
            cursor = (
                self.database()
                .roadmaps.find({"student_id": student_id}, {"_id": 0})
                .sort("generated_at", DESCENDING)
                .limit(limit)
            )
            return [Roadmap.model_validate(item) async for item in cursor]
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def next_version(self, student_id: str) -> int:
        try:
            latest = await self.database().roadmaps.find_one(
                {"student_id": student_id}, {"version": 1}, sort=[("version", DESCENDING)]
            )
            return int(latest["version"]) + 1 if latest else 1
        except PyMongoError as exc:
            raise ApplicationError() from exc
