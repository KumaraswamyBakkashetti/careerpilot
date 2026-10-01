from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from app.core.errors import ErrorResponse
from app.modules.knowledge.models import (
    CompanyContext,
    Entity,
    EntityPage,
    GraphEvidence,
    RelationsPage,
)
from app.modules.knowledge.service import KnowledgeService

router = APIRouter(
    prefix="/knowledge", tags=["Career knowledge"], responses={503: {"model": ErrorResponse}}
)
Id = Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]{2,79}$")]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=10000)]
Search = Annotated[str, Query(max_length=80)]


def service(request: Request) -> KnowledgeService:
    result: KnowledgeService = request.app.state.knowledge
    return result


Service = Annotated[KnowledgeService, Depends(service)]


@router.get("/roles", response_model=EntityPage)
async def roles(s: Service, q: Search = "", limit: Limit = 50, offset: Offset = 0) -> EntityPage:
    return await s.list_entities("Role", q.strip(), limit, offset)


@router.get("/roles/{identifier}", response_model=Entity)
async def role(identifier: Id, s: Service) -> Entity:
    return await s.entity(identifier, "Role")


@router.get("/roles/{identifier}/skills", response_model=RelationsPage)
async def role_skills(
    identifier: Id, s: Service, limit: Limit = 50, offset: Offset = 0
) -> RelationsPage:
    return await s.related(identifier, "Role", "REQUIRES_SKILL", limit=limit, offset=offset)


@router.get("/skills/{identifier}", response_model=Entity)
async def skill(identifier: Id, s: Service) -> Entity:
    return await s.entity(identifier, "Skill")


@router.get("/skills", response_model=EntityPage)
async def skills(s: Service, q: Search = "", limit: Limit = 100, offset: Offset = 0) -> EntityPage:
    return await s.list_entities("Skill", q.strip(), limit, offset)


@router.get("/skills/{identifier}/resources", response_model=RelationsPage)
async def resources(
    identifier: Id, s: Service, limit: Limit = 50, offset: Offset = 0
) -> RelationsPage:
    return await s.related(identifier, "Skill", "TEACHES_SKILL", True, limit, offset)


@router.get("/skills/{identifier}/topics", response_model=RelationsPage)
async def topics(
    identifier: Id, s: Service, limit: Limit = 50, offset: Offset = 0
) -> RelationsPage:
    return await s.related(identifier, "Skill", "ASSESSES_SKILL", True, limit, offset)


@router.get("/resources/{identifier}/topics", response_model=RelationsPage)
async def resource_topics(
    identifier: Id, s: Service, limit: Limit = 50, offset: Offset = 0
) -> RelationsPage:
    return await s.related(identifier, "Resource", "COVERS_TOPIC", limit=limit, offset=offset)


@router.get("/assertions/{identifier}/provenance", response_model=GraphEvidence)
async def provenance(identifier: Id, s: Service) -> GraphEvidence:
    return await s.evidence(identifier)


@router.get("/company-roles", response_model=EntityPage)
async def company_roles(
    s: Service, q: Search = "", limit: Limit = 50, offset: Offset = 0
) -> EntityPage:
    return await s.list_entities("CompanyRole", q.strip(), limit, offset)


@router.get("/company-roles/{identifier}/context", response_model=CompanyContext)
async def context(identifier: Id, s: Service) -> CompanyContext:
    return await s.company_context(identifier)


@router.get("/company-roles/{identifier}/skills", response_model=RelationsPage)
async def company_skills(
    identifier: Id, s: Service, limit: Limit = 50, offset: Offset = 0
) -> RelationsPage:
    return await s.related(identifier, "CompanyRole", "REQUIRES_SKILL", limit=limit, offset=offset)
