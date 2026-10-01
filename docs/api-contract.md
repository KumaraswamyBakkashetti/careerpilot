# API conventions

Application APIs live under `/api/v1`. Infrastructure diagnostics use unversioned `/health/live` and `/health/ready`; they are not business APIs. `/api/v1/system` describes identity, version and implemented phase.

## Success

Typed payloads are returned directly without a generic success envelope. Liveness returns HTTP 200 with `status: alive`. Readiness returns HTTP 200 with `status: ready` and `dependencies.mongodb` and `dependencies.neo4j` set to `up`.

## Errors

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "The requested endpoint does not exist.",
    "request_id": "example-request"
  }
}
```

Readiness HTTP 503 additionally retains its typed health payload:

```json
{
  "status": "not_ready",
  "dependencies": { "mongodb": "down", "neo4j": "up" },
  "error": {
    "code": "DEPENDENCY_UNAVAILABLE",
    "message": "A required service is unavailable.",
    "request_id": "example-request"
  }
}
```

| Status | Code | Policy |
| --- | --- | --- |
| 404 | `NOT_FOUND` | No echo of supplied URL |
| 405 | `METHOD_NOT_ALLOWED` | Preserve `Allow` header |
| 422 | `VALIDATION_ERROR` | No raw input/context echo |
| 503 | `DEPENDENCY_UNAVAILABLE` | No credentials or driver details |
| 500 | `INTERNAL_ERROR` | No traceback, even with debug enabled |

No validation-only test endpoint is shipped. Tests install temporary routes into isolated app factories to exercise real FastAPI validation and exception paths. Framework CORS preflight rejections follow the CORS middleware's HTTP 400 behavior, not the application error schema.

`X-Request-ID` accepts only `[A-Za-z0-9_-]{1,64}`; otherwise a new 32-character UUID hex ID is generated. It appears in response headers, error payloads, request state and logs. It is correlation metadata, never authorization. CORS exposes it to permitted browser origins. Responses also carry `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`.

The frontend validates health bodies at runtime, not only via TypeScript assertions. It accepts readiness 503 as a reachable backend with unavailable dependencies. Other HTTP failures become normalized `ApiError` values, retaining status/code/request ID while suppressing raw error messages. Network failures, deadlines and cancellation have distinct codes. Requests omit credentials until real authentication is implemented.
