import logging
from typing import Literal

from fastapi import Request
from pydantic import BaseModel
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.core.logging import request_id_context


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def error_detail(code: str, message: str) -> ErrorDetail:
    return ErrorDetail(code=code, message=message, request_id=request_id_context.get() or "unknown")


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorResponse(error=error_detail(code, message)).model_dump(),
    )


ErrorCode = Literal[
    "DEPENDENCY_UNAVAILABLE",
    "KNOWLEDGE_NOT_FOUND",
    "KNOWLEDGE_INCONSISTENT",
    "AUTH_NOT_CONFIGURED",
    "AUTHENTICATION_REQUIRED",
    "INVALID_CREDENTIALS",
    "ACCOUNT_EXISTS",
    "PROFILE_NOT_FOUND",
    "TARGET_ROLE_NOT_FOUND",
    "EMPTY_RESUME",
    "RESUME_TOO_LARGE",
    "UNSUPPORTED_RESUME_TYPE",
    "INVALID_RESUME",
    "INVALID_FILENAME",
    "DUPLICATE_RESUME",
    "RESUME_EXTRACTION_FAILED",
    "RESUME_NOT_FOUND",
    "EVIDENCE_NOT_FOUND",
    "INVALID_SKILL_MAPPING",
    "SKILL_NOT_FOUND",
    "GAP_ANALYSIS_NOT_FOUND",
    "RETRIEVAL_INDEX_UNAVAILABLE",
    "RETRIEVAL_INDEX_INCOMPATIBLE",
    "RETRIEVAL_LIMIT_EXCEEDED",
    "RETRIEVAL_TRACE_NOT_FOUND",
    "LLM_NOT_CONFIGURED",
    "MODEL_UNAVAILABLE",
    "MODEL_FORBIDDEN",
    "PROVIDER_UNAVAILABLE",
    "RATE_LIMITED",
    "INVALID_PROVIDER_CONFIGURATION",
    "INVALID_STRUCTURED_OUTPUT_CONFIGURATION",
    "ROADMAP_EVIDENCE_INSUFFICIENT",
    "ROADMAP_SCHEMA_INVALID",
    "ROADMAP_GROUNDING_INVALID",
    "ROADMAP_EVIDENCE_REFERENCE_INVALID",
    "ROADMAP_NOT_FOUND",
    "ROADMAP_GENERATION_IN_PROGRESS",
    "COMPANY_NOT_FOUND",
    "COMPANY_ROLE_NOT_FOUND",
    "COMPANY_ROLE_MISMATCH",
    "COMPANY_EVIDENCE_INSUFFICIENT",
    "COMPANY_SCHEMA_INVALID",
    "COMPANY_GROUNDING_INVALID",
    "COMPANY_PREPARATION_NOT_FOUND",
    "COMPANY_PREPARATION_IN_PROGRESS",
    "INTERVIEW_EVIDENCE_INSUFFICIENT",
    "INTERVIEW_SCHEMA_INVALID",
    "INTERVIEW_GROUNDING_INVALID",
    "INTERVIEW_GENERATION_IN_PROGRESS",
    "INTERVIEW_NOT_FOUND",
    "INTERVIEW_QUESTION_NOT_FOUND",
    "INVALID_INTERVIEW_STATE",
    "DUPLICATE_INTERVIEW_RESPONSE",
    "INTERVIEW_EVALUATION_INVALID",
    "READINESS_NOT_FOUND",
    "READINESS_CALCULATION_IN_PROGRESS",
    "ORCHESTRATION_NOT_FOUND",
]


class ApplicationError(Exception):
    def __init__(self, code: ErrorCode = "DEPENDENCY_UNAVAILABLE") -> None:
        self.code = code


async def application_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApplicationError)
    statuses = {
        "DEPENDENCY_UNAVAILABLE": (503, "A required service is unavailable."),
        "KNOWLEDGE_NOT_FOUND": (404, "The requested knowledge entity does not exist."),
        "KNOWLEDGE_INCONSISTENT": (500, "Stored knowledge failed validation."),
        "AUTH_NOT_CONFIGURED": (503, "Authentication is not configured."),
        "AUTHENTICATION_REQUIRED": (401, "Authentication is required."),
        "INVALID_CREDENTIALS": (401, "Authentication failed."),
        "ACCOUNT_EXISTS": (409, "An account with that identity already exists."),
        "PROFILE_NOT_FOUND": (404, "The requested profile does not exist."),
        "TARGET_ROLE_NOT_FOUND": (404, "The selected canonical role does not exist."),
        "EMPTY_RESUME": (422, "The resume file is empty."),
        "RESUME_TOO_LARGE": (413, "The resume exceeds the configured size limit."),
        "UNSUPPORTED_RESUME_TYPE": (415, "Only matching PDF and DOCX files are supported."),
        "INVALID_RESUME": (422, "The resume file is malformed or cannot be safely read."),
        "INVALID_FILENAME": (422, "The uploaded filename is unsafe."),
        "DUPLICATE_RESUME": (409, "This resume was already uploaded."),
        "RESUME_EXTRACTION_FAILED": (422, "The resume has no supported extractable text."),
        "RESUME_NOT_FOUND": (404, "The requested resume does not exist."),
        "EVIDENCE_NOT_FOUND": (404, "The requested evidence does not exist."),
        "INVALID_SKILL_MAPPING": (422, "The evidence decision requires a valid canonical skill."),
        "SKILL_NOT_FOUND": (404, "The selected canonical skill does not exist."),
        "GAP_ANALYSIS_NOT_FOUND": (404, "The requested gap analysis does not exist."),
        "RETRIEVAL_INDEX_UNAVAILABLE": (503, "The semantic retrieval index is unavailable."),
        "RETRIEVAL_INDEX_INCOMPATIBLE": (503, "The semantic retrieval index is stale."),
        "RETRIEVAL_LIMIT_EXCEEDED": (422, "The requested retrieval limit is too large."),
        "RETRIEVAL_TRACE_NOT_FOUND": (404, "The requested retrieval trace does not exist."),
        "LLM_NOT_CONFIGURED": (503, "Grounded generation is not configured."),
        "MODEL_UNAVAILABLE": (503, "The configured generation model is unavailable."),
        "MODEL_FORBIDDEN": (503, "The configured model is not available to this project."),
        "PROVIDER_UNAVAILABLE": (503, "Grounded generation is temporarily unavailable."),
        "RATE_LIMITED": (429, "Grounded generation is rate limited. Try again later."),
        "INVALID_PROVIDER_CONFIGURATION": (503, "Generation configuration is invalid."),
        "INVALID_STRUCTURED_OUTPUT_CONFIGURATION": (
            503,
            "The structured-output configuration was rejected.",
        ),
        "ROADMAP_EVIDENCE_INSUFFICIENT": (
            422,
            "Validated evidence is insufficient to generate a roadmap.",
        ),
        "ROADMAP_SCHEMA_INVALID": (502, "The generated roadmap failed schema validation."),
        "ROADMAP_GROUNDING_INVALID": (502, "The generated roadmap failed grounding validation."),
        "ROADMAP_EVIDENCE_REFERENCE_INVALID": (
            502,
            "The generated roadmap contains an invalid evidence reference.",
        ),
        "ROADMAP_NOT_FOUND": (404, "The requested roadmap does not exist."),
        "ROADMAP_GENERATION_IN_PROGRESS": (
            409,
            "An identical roadmap generation request is already in progress.",
        ),
        "COMPANY_NOT_FOUND": (404, "The canonical company does not exist."),
        "COMPANY_ROLE_NOT_FOUND": (404, "The canonical company role does not exist."),
        "COMPANY_ROLE_MISMATCH": (422, "The gap snapshot targets a different generic role."),
        "COMPANY_EVIDENCE_INSUFFICIENT": (422, "Validated company-role evidence is insufficient."),
        "COMPANY_SCHEMA_INVALID": (502, "Generated company preparation failed schema validation."),
        "COMPANY_GROUNDING_INVALID": (
            502,
            "Generated company preparation failed grounding validation.",
        ),
        "COMPANY_PREPARATION_NOT_FOUND": (404, "The company preparation does not exist."),
        "COMPANY_PREPARATION_IN_PROGRESS": (
            409,
            "An identical company preparation is in progress.",
        ),
        "INTERVIEW_EVIDENCE_INSUFFICIENT": (422, "Validated interview evidence is insufficient."),
        "INTERVIEW_SCHEMA_INVALID": (502, "Generated interview content failed schema validation."),
        "INTERVIEW_GROUNDING_INVALID": (
            502,
            "Generated interview content failed grounding validation.",
        ),
        "INTERVIEW_GENERATION_IN_PROGRESS": (409, "An identical interview is being generated."),
        "INTERVIEW_NOT_FOUND": (404, "The interview session does not exist."),
        "INTERVIEW_QUESTION_NOT_FOUND": (404, "The interview question does not exist."),
        "INVALID_INTERVIEW_STATE": (409, "The interview is not in the required state."),
        "DUPLICATE_INTERVIEW_RESPONSE": (409, "This question already has an immutable response."),
        "INTERVIEW_EVALUATION_INVALID": (502, "The interview evaluation failed validation."),
        "READINESS_NOT_FOUND": (404, "The readiness snapshot does not exist."),
        "READINESS_CALCULATION_IN_PROGRESS": (
            409,
            "An identical readiness calculation is in progress.",
        ),
        "ORCHESTRATION_NOT_FOUND": (404, "The orchestration trace does not exist."),
    }
    status, message = statuses[exc.code]
    return error_response(status, exc.code, message)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Pydantic details can contain supplied values, credentials and exception contexts.
    return error_response(422, "VALIDATION_ERROR", "The request does not match the API contract.")


async def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    if exc.status_code == 404:
        return error_response(404, "NOT_FOUND", "The requested endpoint does not exist.")
    if exc.status_code == 405:
        response = error_response(405, "METHOD_NOT_ALLOWED", "This method is not supported.")
        if exc.headers and "Allow" in exc.headers:
            response.headers["Allow"] = exc.headers["Allow"]
        return response
    return error_response(exc.status_code, "HTTP_ERROR", "The request could not be completed.")


def internal_error_response(exc: Exception) -> JSONResponse:
    logging.getLogger("careerpilot.errors").error(
        "request_failed", extra={"category": type(exc).__name__}
    )
    return error_response(500, "INTERNAL_ERROR", "An unexpected error occurred.")
