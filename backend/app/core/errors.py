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


class ApplicationError(Exception):
    def __init__(self, code: Literal["DEPENDENCY_UNAVAILABLE"] = "DEPENDENCY_UNAVAILABLE") -> None:
        self.code = code


async def application_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApplicationError)
    return error_response(503, exc.code, "A required service is unavailable.")


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
