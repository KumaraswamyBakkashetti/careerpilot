# API conventions

## Canonical knowledge reads

All canonical knowledge reads live below `/api/v1/knowledge`:

- `GET /roles?q=&limit=&offset=` and `GET /roles/{id}`
- `GET /roles/{id}/skills`
- `GET /skills/{id}`, `/skills/{id}/resources`, and `/skills/{id}/topics`
- `GET /resources/{id}/topics`
- `GET /assertions/{id}/provenance`
- `GET /company-roles`, `/company-roles/{id}/context`, and `/company-roles/{id}/skills`

List results are ordered by name then stable ID. `limit` is 1–100 and `offset` is 0–10000. IDs use lowercase canonical syntax. Related-entity results embed assertion and provenance source metadata. Missing knowledge uses `KNOWLEDGE_NOT_FOUND`/404; unavailable Neo4j uses `DEPENDENCY_UNAVAILABLE`/503; inconsistent stored knowledge uses sanitized `KNOWLEDGE_INCONSISTENT`/500. Graph mutation is intentionally absent from HTTP.

Application APIs live under `/api/v1`. Infrastructure diagnostics use unversioned `/health/live` and `/health/ready`; they are not business APIs. `/api/v1/system` describes identity, version and implemented phase.

`GET /skills` is also available as a bounded canonical picker for evidence correction.

## Private student APIs

`POST /auth/register` and `POST /auth/token` issue short-lived bearer JWTs. All `/student` routes require that token and derive ownership exclusively from its signed subject. Private identifiers are opaque and every repository lookup also filters on the authenticated owner.

- `GET|PUT /student/profile`
- `POST|GET /student/resumes`
- `POST /student/resumes/{id}/process`
- `DELETE /student/resumes/{id}`
- `GET /student/resumes/{id}/evidence` and `GET /student/evidence`
- `PUT /student/evidence/{id}` with `CONFIRM` or `REJECT`
- `POST /student/gap-analyses` and `GET /student/gap-analyses/{id}`

Uploads use multipart field `file` and return the resume after synchronous processing. An extraction or normalization failure returns a safe error while retaining an explicit retryable record. Private resume responses exclude `student_id` and never expose a storage key or filesystem path.

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
| 401 | `AUTHENTICATION_REQUIRED` / `INVALID_CREDENTIALS` | Generic authentication failure |
| 404 | `NOT_FOUND` | No echo of supplied URL |
| 413 | `RESUME_TOO_LARGE` | Configured bounded upload |
| 415 | `UNSUPPORTED_RESUME_TYPE` | Extension, MIME, and signature must agree |
| 405 | `METHOD_NOT_ALLOWED` | Preserve `Allow` header |
| 422 | `VALIDATION_ERROR` | No raw input/context echo |
| 503 | `DEPENDENCY_UNAVAILABLE` | No credentials or driver details |
| 500 | `INTERNAL_ERROR` | No traceback, even with debug enabled |

No validation-only test endpoint is shipped. Tests install temporary routes into isolated app factories to exercise real FastAPI validation and exception paths. Framework CORS preflight rejections follow the CORS middleware's HTTP 400 behavior, not the application error schema.

`X-Request-ID` accepts only `[A-Za-z0-9_-]{1,64}`; otherwise a new 32-character UUID hex ID is generated. It appears in response headers, error payloads, request state and logs. It is correlation metadata, never authorization. CORS exposes it to permitted browser origins. Responses also carry `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`.

The frontend validates health, knowledge, and student bodies at runtime, not only via TypeScript assertions. It accepts readiness 503 as a reachable backend with unavailable dependencies. Other HTTP failures become normalized `ApiError` values, retaining status/code/request ID while suppressing raw error messages. Network failures, deadlines and cancellation have distinct codes. Private requests use an in-memory bearer token and omit browser credentials.
# Phase 4 retrieval routes

All retrieval routes require the same bearer identity as private student routes. `POST /api/v1/retrieval/search` accepts only the finite `ROLE_REQUIREMENTS` or `SKILL_RESOURCES` task contract. `POST /api/v1/retrieval/skills/{skill_id}/resources` retrieves canonical graph and passage evidence. `POST /api/v1/retrieval/gaps/{gap_run_id}/evidence` verifies ownership and binds retrieval to a gap item. `GET /api/v1/retrieval/traces/{trace_id}` is owner-filtered. Responses are typed `EvidenceBundle`/`RetrievalTrace` records; no route exposes embeddings, raw FAISS objects, arbitrary paths or rebuild operations.
