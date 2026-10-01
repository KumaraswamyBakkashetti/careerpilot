from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.infrastructure.mongodb import MongoDBAdapter
from app.infrastructure.neo4j import Neo4jAdapter


async def test_mongo_driver_lifecycle(settings: Settings) -> None:
    client = MagicMock()
    client.__getitem__.return_value.command = AsyncMock()
    client.close = AsyncMock()
    with patch("app.infrastructure.mongodb.AsyncMongoClient", return_value=client) as factory:
        adapter = MongoDBAdapter(settings)
        await adapter.start()
        await adapter.ping()
        factory.assert_called_once()
        assert factory.call_args.kwargs["serverSelectionTimeoutMS"] == 100
        client.__getitem__.assert_called_once_with("careerpilot_dev")
        client.__getitem__.return_value.command.assert_awaited_once_with("ping")
        await adapter.close()
        await adapter.close()
        client.close.assert_awaited_once()
        assert adapter.client is None


async def test_neo4j_driver_lifecycle(settings: Settings) -> None:
    settings.neo4j_password = SecretStr("test-only-password")
    driver = MagicMock()
    driver.verify_connectivity = AsyncMock()
    driver.close = AsyncMock()
    session = driver.session.return_value.__aenter__.return_value
    session.run = AsyncMock()
    session.run.return_value.consume = AsyncMock()
    with patch(
        "app.infrastructure.neo4j.AsyncGraphDatabase.driver", return_value=driver
    ) as factory:
        adapter = Neo4jAdapter(settings)
        await adapter.start()
        await adapter.ping()
        assert factory.call_args.kwargs["connection_timeout"] == 0.1
        driver.verify_connectivity.assert_awaited_once()
        driver.session.assert_called_once_with(database="neo4j")
        session.run.assert_awaited_once_with("RETURN 1 AS connected")
        session.run.return_value.consume.assert_awaited_once()
        await adapter.close()
        await adapter.close()
        driver.close.assert_awaited_once()
        assert adapter.driver is None


@pytest.mark.parametrize("adapter_type", [MongoDBAdapter, Neo4jAdapter])
async def test_uninitialized_adapter_fails(settings: Settings, adapter_type: type) -> None:
    adapter = adapter_type(settings)
    with pytest.raises(RuntimeError):
        await adapter.ping()
    await adapter.close()


async def test_missing_neo4j_password_fails_honestly(settings: Settings) -> None:
    adapter = Neo4jAdapter(settings)
    with pytest.raises(RuntimeError, match="not configured"):
        await adapter.start()
    assert adapter.driver is None


@pytest.mark.parametrize("adapter_type", [MongoDBAdapter, Neo4jAdapter])
async def test_driver_failure_propagates(settings: Settings, adapter_type: type) -> None:
    adapter = adapter_type(settings)
    if isinstance(adapter, MongoDBAdapter):
        client = MagicMock()
        client.__getitem__.return_value.command = AsyncMock(side_effect=ConnectionError("private"))
        adapter.client = client
    else:
        driver = MagicMock()
        driver.verify_connectivity = AsyncMock(side_effect=ConnectionError("private"))
        adapter.driver = driver
    with pytest.raises(ConnectionError):
        await adapter.ping()
