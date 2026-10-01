from typing import TypeVar

from app.core.errors import ApplicationError
from app.modules.knowledge.models import (
    CompanyContext,
    Entity,
    EntityPage,
    GraphEvidence,
    Kind,
    RelationsPage,
    RelationType,
)
from app.modules.knowledge.repository import KnowledgeRepository

T = TypeVar("T")


class KnowledgeService:
    def __init__(self, repository: KnowledgeRepository) -> None:
        self.repository = repository

    @staticmethod
    def found(value: T | None) -> T:
        if value is None:
            raise ApplicationError("KNOWLEDGE_NOT_FOUND")
        return value

    async def list_entities(self, kind: Kind, query: str, limit: int, offset: int) -> EntityPage:
        return await self.repository.list_entities(kind, query, limit, offset)

    async def entity(self, identifier: str, kind: Kind) -> Entity:
        return self.found(await self.repository.entity(identifier, kind))

    async def related(
        self,
        identifier: str,
        kind: Kind,
        relation: RelationType,
        incoming: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> RelationsPage:
        return self.found(
            await self.repository.related(identifier, kind, relation, incoming, limit, offset)
        )

    async def evidence(self, identifier: str) -> GraphEvidence:
        return self.found(await self.repository.evidence(identifier))

    async def company_context(self, identifier: str) -> CompanyContext:
        return self.found(await self.repository.company_context(identifier))
