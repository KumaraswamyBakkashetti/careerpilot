from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import PyMongoError

from app.core.errors import ApplicationError
from app.infrastructure.mongodb import MongoDBAdapter
from app.modules.retrieval.models import RetrievalTrace


class MongoRetrievalTraceRepository:
    def __init__(self, adapter: MongoDBAdapter) -> None:
        self.adapter = adapter

    def database(self) -> Any:
        if self.adapter.client is None:
            raise ApplicationError()
        return self.adapter.client[self.adapter.settings.mongodb_database]

    async def initialize(self) -> None:
        try:
            await self.database().retrieval_traces.create_indexes(
                [
                    IndexModel("trace_id", unique=True),
                    IndexModel([("student_id", ASCENDING), ("created_at", DESCENDING)]),
                ]
            )
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def save(self, trace: RetrievalTrace) -> None:
        try:
            await self.database().retrieval_traces.insert_one(trace.model_dump(mode="python"))
        except PyMongoError as exc:
            raise ApplicationError() from exc

    async def get(self, student_id: str, trace_id: str) -> RetrievalTrace | None:
        try:
            value = await self.database().retrieval_traces.find_one(
                {"student_id": student_id, "trace_id": trace_id}, {"_id": 0}
            )
            return RetrievalTrace.model_validate(value) if value else None
        except PyMongoError as exc:
            raise ApplicationError() from exc
