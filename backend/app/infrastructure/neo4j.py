from neo4j import AsyncDriver, AsyncGraphDatabase

from app.core.config import Settings


class Neo4jAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.driver: AsyncDriver | None = None

    async def start(self) -> None:
        if not self.settings.neo4j_password.get_secret_value():
            raise RuntimeError("Neo4j credentials are not configured")
        self.driver = AsyncGraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password.get_secret_value()),
            connection_timeout=self.settings.dependency_timeout_seconds,
            connection_acquisition_timeout=self.settings.dependency_timeout_seconds,
            max_transaction_retry_time=0,
            max_connection_pool_size=20,
        )

    async def ping(self) -> None:
        if self.driver is None:
            raise RuntimeError("Neo4j adapter is not initialized")
        await self.driver.verify_connectivity()
        # Verify the configured database, beyond the initial driver handshake.
        async with self.driver.session(database=self.settings.neo4j_database) as session:
            result = await session.run("RETURN 1 AS connected")
            await result.consume()

    async def close(self) -> None:
        if self.driver is not None:
            try:
                await self.driver.close()
            finally:
                self.driver = None
