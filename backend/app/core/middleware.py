import logging
import re
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import internal_error_response
from app.core.logging import request_id_context


class SanitizedErrorsMiddleware:
    """Catch unhandled errors inside CORS and request context, before sending a response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def track_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, track_send)
        except Exception as exc:
            response = internal_error_response(exc)
            if started:
                raise  # A partially sent response cannot safely be replaced.
            await response(scope, receive, send)


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        supplied = Headers(scope=scope).get("X-Request-ID", "")
        request_id = supplied if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", supplied) else uuid4().hex
        token = request_id_context.set(request_id)
        scope.setdefault("state", {})["request_id"] = request_id
        start = perf_counter()
        status = 500

        async def response_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Cache-Control"] = "no-store"
            await send(message)

        try:
            await self.app(scope, receive, response_send)
        finally:
            route = scope.get("route")
            logging.getLogger("careerpilot.requests").info(
                "request_completed",
                extra={
                    "method": scope["method"],
                    # Route templates avoid logging private identifiers or attacker-supplied paths.
                    "route": getattr(route, "path", "<unmatched>"),
                    "status": status,
                    "duration_ms": round((perf_counter() - start) * 1000, 2),
                },
            )
            request_id_context.reset(token)
