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
