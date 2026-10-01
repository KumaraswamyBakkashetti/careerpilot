from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, Path, Query, Request, Response, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import ApplicationError, ErrorResponse
from app.modules.student.models import (
    EvidenceDecision,
    GapAnalysisRun,
    LoginRequest,
    ProfileUpdate,
    RegisterRequest,
    ResumeView,
    SkillEvidence,
    StudentIdentity,
    StudentProfile,
    TokenResponse,
)
from app.modules.student.service import StudentService

router = APIRouter(
    tags=["Student intelligence"],
    responses={401: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
bearer = HTTPBearer(auto_error=False)
PrivatePath = Annotated[str, Path(pattern=r"^(resume|evidence|gap)_[a-f0-9]{32}$")]


def service(request: Request) -> StudentService:
    result: StudentService = request.app.state.student
    return result


async def identity(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> StudentIdentity:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise ApplicationError("AUTHENTICATION_REQUIRED")
    return service(request).auth.identity(credentials.credentials)


Service = Annotated[StudentService, Depends(service)]
Identity = Annotated[StudentIdentity, Depends(identity)]


@router.post("/auth/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, value: Service) -> TokenResponse:
    return await value.register(body)


@router.post("/auth/token", response_model=TokenResponse)
async def token(body: LoginRequest, value: Service) -> TokenResponse:
    return await value.login(body)


@router.get("/student/profile", response_model=StudentProfile)
async def profile(owner: Identity, value: Service) -> StudentProfile:
    return await value.profile(owner.student_id)


@router.put("/student/profile", response_model=StudentProfile)
async def update_profile(body: ProfileUpdate, owner: Identity, value: Service) -> StudentProfile:
    return await value.update_profile(owner.student_id, body.display_name, body.target_role_id)


@router.post("/student/resumes", response_model=ResumeView)
async def upload_resume(
    owner: Identity,
    value: Service,
    file: Annotated[UploadFile, File()],
    content_length: Annotated[int | None, Header(ge=0)] = None,
) -> ResumeView:
    if content_length is not None and content_length > value.settings.resume_max_bytes + 100_000:
        raise ApplicationError("RESUME_TOO_LARGE")
    content = await file.read(value.settings.resume_max_bytes + 1)
    if len(content) > value.settings.resume_max_bytes:
        raise ApplicationError("RESUME_TOO_LARGE")
    return await value.upload(
        owner.student_id,
        file.filename or "",
        file.content_type or "application/octet-stream",
        content,
    )


@router.get("/student/resumes", response_model=list[ResumeView])
async def resumes(
    owner: Identity, value: Service, limit: Annotated[int, Query(ge=1, le=50)] = 20
) -> list[ResumeView]:
    return await value.list_resumes(owner.student_id, limit)


@router.post("/student/resumes/{resume_id}/process", response_model=ResumeView)
async def retry_resume(resume_id: PrivatePath, owner: Identity, value: Service) -> ResumeView:
    return await value.retry(owner.student_id, resume_id)


@router.delete("/student/resumes/{resume_id}", status_code=204)
async def delete_resume(resume_id: PrivatePath, owner: Identity, value: Service) -> Response:
    await value.delete_resume(owner.student_id, resume_id)
    return Response(status_code=204)


@router.get("/student/resumes/{resume_id}/evidence", response_model=list[SkillEvidence])
async def resume_evidence(
    resume_id: PrivatePath, owner: Identity, value: Service
) -> list[SkillEvidence]:
    return await value.evidence(owner.student_id, resume_id)


@router.get("/student/evidence", response_model=list[SkillEvidence])
async def all_evidence(owner: Identity, value: Service) -> list[SkillEvidence]:
    return await value.evidence(owner.student_id, None)


@router.put("/student/evidence/{evidence_id}", response_model=SkillEvidence)
async def decide_evidence(
    evidence_id: PrivatePath, body: EvidenceDecision, owner: Identity, value: Service
) -> SkillEvidence:
    return await value.decide(owner.student_id, evidence_id, body)


@router.post("/student/gap-analyses", response_model=GapAnalysisRun, status_code=201)
async def analyze(owner: Identity, value: Service) -> GapAnalysisRun:
    return await value.analyze(owner.student_id)


@router.get("/student/gap-analyses/{run_id}", response_model=GapAnalysisRun)
async def gap(run_id: PrivatePath, owner: Identity, value: Service) -> GapAnalysisRun:
    return await value.gap(owner.student_id, run_id)
