from typing import Any

from pymongo import AsyncMongoClient

from app.core.config import Settings


class MongoDBAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: AsyncMongoClient[dict[str, Any]] | None = None

    async def start(self) -> None:
        timeout_ms = int(self.settings.dependency_timeout_seconds * 1000)
        self.client = AsyncMongoClient(
            self.settings.mongodb_uri.get_secret_value(),
            serverSelectionTimeoutMS=timeout_ms,
            connectTimeoutMS=timeout_ms,
            socketTimeoutMS=timeout_ms,
            timeoutMS=timeout_ms,
            maxPoolSize=20,
            appname="CareerPilot",
        )

    async def ping(self) -> None:
        if self.client is None:
            raise RuntimeError("MongoDB adapter is not initialized")
        await self.client[self.settings.mongodb_database].command("ping")

    async def close(self) -> None:
        if self.client is not None:
            try:
                await self.client.close()
            finally:
                self.client = None
