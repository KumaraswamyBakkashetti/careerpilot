from typing import Protocol

from app.modules.knowledge.models import (
    CompanyContext,
    Entity,
    EntityPage,
    GraphEvidence,
    Kind,
    RelationsPage,
    RelationType,
)


class KnowledgeRepository(Protocol):
    async def list_entities(
        self, kind: Kind, query: str, limit: int, offset: int
    ) -> EntityPage: ...
    async def entity(self, identifier: str, kind: Kind) -> Entity | None: ...
    async def related(
        self,
        identifier: str,
        kind: Kind,
        relation: RelationType,
        incoming: bool,
        limit: int,
        offset: int,
    ) -> RelationsPage | None: ...
    async def evidence(self, identifier: str) -> GraphEvidence | None: ...
    async def company_context(self, identifier: str) -> CompanyContext | None: ...
