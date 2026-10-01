# CareerPilot — Phase 1 Engineering Foundation Report

Verification date: **2026-10-01**, Asia/Calcutta. Project version: **0.1.0**.

## 1. Executive Summary

Phase 1 establishes a runnable React/TypeScript frontend and one FastAPI modular monolith, with real asynchronous MongoDB/Neo4j adapters, typed configuration, bounded lifecycle management, health contracts, sanitized failures, JSON logging and request IDs.

**Final automated results: 74 passed, 0 failed, 0 skipped** with integration explicitly enabled: 56 backend tests and 18 frontend tests. Formatting, lint, typing, frontend production build, backend container build and the full local quality gate passed. Real database connectivity, HTTP integration, outage behavior, recovery and container shutdown were executed.

All 39 stated engineering exit criteria are satisfied by the evidence below. Browser visual inspection and execution of the GitHub-hosted workflow remain **NOT VERIFIED**. They are not represented as passes. No Phase 2+ functionality or KA-RAG research results are claimed.

## 2. Architecture Implemented

```text
React + TypeScript + Vite
         |
Central API client / health contract validation
         |
FastAPI routers + request context + error policy
         |
Application health service / Dependency protocol
         |
MongoDB adapter        Neo4j adapter
         |                    |
Student/application    Canonical career-domain
state store            knowledge store
```

`app/main.py` is the composition root. HTTP contracts depend on an application service; the service depends on a protocol; database drivers are isolated in infrastructure. There is one backend process and no microservices. Domain module folders will be introduced with actual use cases rather than empty placeholders.

## 3. Repository Structure

```text
CareerPilot/
  backend/
    app/{api,application,core,infrastructure}/
    tests/
    pyproject.toml, uv.lock, Dockerfile
  frontend/
    src/{app,api,test}/
    package.json, package-lock.json, vite.config.ts, tsconfig.json
  docs/
    architecture/{ADR-001-modular-monolith.md,phase1.md}
    api-contract.md
  scripts/{setup-env.ps1,start-integration.ps1,check.ps1,verify-runtime.mjs}
  .github/workflows/quality.yml
  .env.example, .gitignore, compose.yaml, compose.test.yaml
  README.md, PHASE1_REPORT.md
```

Workspace-only ignored material: `.tools/`, backend virtual environment, frontend dependencies/build output, local `.env` files and `artifacts/verification/`.

## 4. Files Added

- Backend: application factory/entry point, API routes and schemas, health protocol/service, settings, logging, exception policy, ASGI middleware and two database adapters.
- Backend tests: configuration, API, adapters, lifecycle, integration safety and real integration suites.
- Frontend: React status interface, styling, strict TypeScript configuration, central API client, runtime health decoder and four test files.
- Operations: locked dependencies, backend Dockerfile, development and isolated-test Compose configurations, setup/integration/quality/runtime scripts and CI workflow.
- Documentation: README, API contract, architecture document, modular-monolith ADR and this report.
- Local Git metadata initialized on `main`; no remote, commit, push or deployment.

## 5. Files Modified

No pre-existing source files existed. All project files are new; changes during implementation refined the new foundation. No existing user functionality was deleted or overwritten.

**Baseline inspection:** the workspace had no files, `.git`, frontend, backend, package configuration, tests, Docker configuration or documentation. Ancestor instruction-file checks found no applicable AGENTS.md. Existing project checks were therefore not applicable. Node 24.19.0/npm 11.17.0 were available; Python was absent and Docker was initially stopped. Python 3.12.14/uv 0.12.21 were provisioned locally and the existing Docker Desktop engine was started.

## 6. Configuration

Settings use the `CP_` prefix, avoiding collisions with host variables such as `DEBUG`. The root dotenv path is resolved from the module location; explicit environment values override it. Settings include identity/environment, host/port, fixed `/api/v1`, exact CORS origins, both database configurations, log level and dependency deadlines.

MongoDB URI and Neo4j password use `SecretStr`. Production requires explicit database/CORS configuration, a nonempty Neo4j password, HTTPS CORS origins and debug disabled. Invalid configuration is rejected; the normal application entry point suppresses raw settings exceptions. No production credential is invented.

`.env.example` contains placeholders/defaults only. The setup script creates random ignored local credentials and preserves existing files. Frontend `VITE_API_BASE_URL` is public configuration; `BACKEND_PROXY_TARGET` and optional `CP_VITE_POLLING` control local development. Full variable reference is in README.

## 7. Backend Foundation

- Factory with modern FastAPI lifespan; resources allocated once and reused.
- Dependency initialization/probes/cleanup bounded by configured timeouts.
- Database outages do not prevent serving liveness; readiness reports the actual failed dependencies.
- `/api/v1/system` supplies identity/version/phase. Operational health routes are intentionally unversioned.
- Typed OpenAPI success/error contracts; actual `/openapi.json` and `/docs` responses verified over HTTP.
- Central handlers for validation, HTTP and application errors; unexpected failures become sanitized HTTP 500 inside CORS.
- `X-Request-ID` accepts 1–64 restricted ASCII characters or generates a UUID hex ID. Headers, error payloads, context and logs share it.
- Allowlisted JSON logs include UTC timestamp, level, logger, request ID, method, route template, status and duration. No arbitrary query strings, unmatched paths, driver exception messages, authorization data or request bodies are logged.
- Explicit CORS origins, credentials disabled; security/cache headers on responses.

## 8. MongoDB Integration

PyMongo **4.18.2** `AsyncMongoClient` provides one pooled client per lifespan. Server selection, connection, socket and operation deadlines are configured. Ping executes against the selected database. Close is awaited and references are cleared. No collections or student schema are created.

**PASSED — real MongoDB 8.0.32** in isolated Compose project on loopback port 27617. Direct adapter ping and real FastAPI readiness passed. Stopping MongoDB yielded liveness 200/readiness 503 (`mongodb: down`, `neo4j: up`); readiness recovered after restart. Invalid MongoDB credentials were also rejected by the real driver and sanitized by the application.

## 9. Neo4j Integration

Neo4j Python driver **6.3.1** uses `AsyncGraphDatabase`, bounded acquisition/connection deadlines, no transaction retry delay, connectivity verification and `RETURN 1` in the configured database. Query results are consumed and sessions/drivers close cleanly. No graph schema or seed data is created.

**PASSED — real Neo4j 5.26.31 Community** in its own isolated container/volume on loopback port 7767. Handshake, selected-database access and real application readiness passed. Stopping Neo4j yielded liveness 200/readiness 503 (`neo4j: down`, `mongodb: up`) and recovered after restart. Wrong credentials and a nonexistent database were exercised against the real driver.

## 10. Frontend Foundation

React renders the exact CareerPilot identity and technical subtitle, with foundation scope clearly distinguished from later product functionality. The page provides loading, healthy, partial outage, unreachable backend, refresh and request-ID states with semantic headings/buttons/status announcements.

All backend communication passes through `ApiClient`: configurable base URL, request IDs, omitted credentials, cancellation/deadline handling and normalized errors. The health decoder validates unknown JSON at runtime and distinguishes readiness 503 from a disconnected backend. No fake authentication, AI chat or placement-readiness scoring exists.

**PASSED — actual client → Vite proxy → FastAPI → both real databases**, using a Node-environment Vitest integration test. React rendering/interaction states passed in jsdom. Vite served actual HTML and proxied health over HTTP. **NOT VERIFIED — visual browser inspection:** both Chrome and in-app browser entry attempts reported unavailable browser control.

## 11. Testing

Final full-suite counts, with explicit integration opt-in:

| Suite | Passed | Failed | Skipped | Scope |
| --- | ---: | ---: | ---: | --- |
| Backend | 56 | 0 | 0 | 50 unit/safety + 6 real database/application integration |
| Frontend | 18 | 0 | 0 | 17 unit/rendering + 1 real client/proxy integration |
| Total | **74** | **0** | **0** | Distinct final test cases; repeat executions not added together |

Exact commands used for final evidence, after assigning the isolated service password to `TEST_NEO4J_PASSWORD` without exposing it:

```powershell
$env:CP_RUN_INTEGRATION = '1'
$env:CP_RUN_FRONTEND_INTEGRATION = '1'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1 -Integration
cd backend
./.venv/Scripts/python.exe -m pytest -q --junitxml=../artifacts/verification/backend.xml
cd ../frontend
npm.cmd test -- --reporter=default --reporter=json --outputFile=../artifacts/verification/frontend.json
```

The quality gate separately reported **50 backend unit tests passed / 6 deselected**, **6 integration tests passed / 50 deselected**, and **18 frontend tests passed**. Deselect counts are not skips or successes.

**SKIPPED:** earlier default runs intentionally skipped real integration. With current suites, a default full backend run skips six database tests and a default frontend run skips one live test; integration opt-in is required. Final enabled evidence has zero skips.

**FAILED during development, then corrected:** the initial backend run had 5 failures/25 setup errors caused by the machine-wide `DEBUG` value; settings were namespaced. A frontend restricted run could not spawn its build tool. Direct PowerShell script execution was blocked by host policy; reviewed scripts ran with a process-only override. One quality-gate attempt had 3 integration failures because the outage experiment overlapped it; the services were restored and the gate rerun serially. These were not pre-existing project test failures and are not hidden as passes.

Tests exercise real configuration validation, ASGI middleware, health state transitions, concurrent request context, API schemas, exception handling and lifecycle. Fakes/mock drivers are confined to boundaries. The integration suite checks actual drivers and both cleanup paths, including invalid credentials/database access. Separate safety tests reject production/non-loopback/default-port targets. No assert-true tests or fake connectivity paths exist.

**NOT VERIFIED:** hosted CI execution, Python 3.13 and native Linux/macOS host workflows. The backend Linux container was actually built and run.

## 12. Build Verification

| Check | Actual result |
| --- | --- |
| uv dependency installation + lock | PASS; Python 3.12.14, uv 0.12.21 |
| Ruff format/check | PASS; 23 Python files formatted/checked |
| Mypy strict application typing | PASS; 15 source files |
| npm dependency installation/lock | PASS |
| Prettier | PASS |
| ESLint with zero warnings | PASS |
| TypeScript project check | PASS |
| Vite production build | PASS; 31 modules transformed |
| Final frontend output | HTML 0.58 kB; CSS 3.42 kB; JS 228.29 kB (71.55 kB gzip) |
| Compose configuration | PASS; `config --quiet` for default/app and isolated workflows |
| Backend container build | PASS; locked runtime dependencies, non-root user |
| Full local quality gate | PASS; stops on failing commands |

## 13. Runtime Verification

Actually started Python/FastAPI locally, Vite locally, isolated MongoDB/Neo4j containers, and the final backend container. Docker **29.7.2**, Compose **5.3.1**. The container was checked on loopback 8001; Vite on 5173 forwarded to it for the final client integration. The local Python backend on 8000 was also probed earlier.

Observed live HTTP 200, ready HTTP 200 with both databases up, versioned system metadata, OpenAPI/Swagger responses, request-ID propagation and allowed-origin CORS. Runtime scripts also checked frontend HTML and proxy readiness contracts.

Container SIGTERM shutdown logged `application_stopping`, `application_stopped`, and Uvicorn `Application shutdown complete`. The container exit status was **143**, reflecting SIGTERM; this is not reported as exit 0. Real adapter lifecycle tests additionally assert client/driver references are cleared. Tests verify that one close failure does not prevent the other cleanup.

Raw local evidence is retained under ignored `artifacts/verification/`: `quality.txt`, `backend.xml`, `frontend.json`, `runtime-ready.json`, `runtime-startup-outage.json`, `runtime-recovered.json`, `runtime-backend-down.json`, `shutdown.txt`, `security.json`, and `npm-audit.json`.

After verification, local frontend/backend verification processes and the disposable integration containers/volumes were stopped/removed. The frontend proxy configuration was restored to its normal local port 8000. Generated root credentials and installed dependencies remain ignored and available for normal development startup. The Docker engine remains running.

## 14. Failure Testing

| Scenario executed | Observed behavior |
| --- | --- |
| Real MongoDB stopped | Liveness 200; readiness 503; only MongoDB down; recovery 200 |
| Real Neo4j stopped | Liveness 200; readiness 503; only Neo4j down; recovery 200 |
| Both databases stopped | Liveness 200; readiness 503; both down; same results via Vite proxy |
| Backend container starts with both DBs stopped | Process starts; live 200; ready 503; after DB restart ready 200 |
| Backend stopped while Vite remains running | Frontend HTML 200; proxy health 500, no false health success |
| Real wrong MongoDB credentials | Driver rejects access; sanitized 503 |
| Real wrong Neo4j credentials/missing database | Driver rejects access; sanitized 503 |
| Slow dependency boundary | Deadline ends probe; readiness 503 |
| Malformed typed request, unknown route, unexpected exception | Real isolated FastAPI routes verify 422, 404 and sanitized 500 with request ID |
| Invalid request ID / concurrent requests | Invalid values replaced; individual IDs preserved and context reset |
| Invalid real startup configuration | Normal entry point returned exit 2 and a sanitized diagnostic without echoing the supplied value |
| Initialization/cleanup failure boundary | Liveness preserved and other resources still cleaned up |

One initial outage-startup harness attempt used `docker compose start backend`, which also started its dependencies, invalidating the both-down expectation. The corrected check used `docker start careerpilot-integration-backend-1` while both test databases remained stopped and passed. A later attempt encountered the Vite watcher interruption; the final stable run passed and evidence was saved. A Node/libuv shutdown assertion also appeared on failed ad hoc verification runs; successful final runtime runs did not reproduce it.

## 15. Security Review

- Reviewed source/configuration for real credentials, tokens/private keys, permissive CORS, raw exception exposure, unsafe logs and driver coupling.
- Scanned all 58 source candidates before adding this report: zero credential/key findings; generated local credential absent from actual backend logs. Root/frontend `.env`, tools, dependencies and build artifacts are Git-ignored.
- Final source/report review scanned 59 source files: zero credential findings and zero trailing-whitespace findings; evidence is in `artifacts/verification/final-source-review.json`.
- Only test-only dummy credential literals exist in test code; real generated values were not printed or added to source.
- `npm audit`: **0 vulnerabilities** after replacing the affected Vitest version and updating supported lint tooling. Initial install had two moderate advisories from the test toolchain; these were remediated.
- `pip-audit` against the installed backend environment: **35 packages checked, no known vulnerabilities found**.
- Production validation, request-ID sanitation, error/CORS contracts, integration-target restrictions and logging allowlist have executed tests.
- Published development/test ports are loopback-bound; backend container uses a non-root user. Private-resource ownership is documented for future authenticated modules, without pretending it exists now.
- No commit, remote, push or deployment was performed.

## 16. Known Limitations

- No controlled browser was available for visual or real browser click-through QA. Rendering/refresh/state behavior was exercised in jsdom; the live frontend client and proxy were exercised separately.
- GitHub-hosted CI is configured but was not triggered. Python 3.13 and native Linux/macOS developer workflows were not run.
- Local Compose is development infrastructure; production auth/TLS/roles, browser deployment/reverse proxy and authenticated ownership require later implementation before accepting private student data.
- Health probes establish bounded infrastructure reachability, not future business-query correctness.
- Environment changes require restart. Missing Neo4j credentials do not silently recover by inventing credentials.
- OneDrive produced a native watcher `EBUSY` when a new env file was created while Vite was running. Optional polling and initializing env first address this workflow; polling startup was verified.

## 17. Technical Debt

- Add browser automation/visual QA when a browser runner is available.
- Confirm the first hosted CI run and add a hosted frontend runtime/browser check when deployment routing is defined.
- Maintain dependency/image pins and vulnerability audits as versions evolve.

Unimplemented future business modules are planned scope, not unfinished Phase 1 placeholders. No failing Phase 1 code-quality check remains.

## 18. Phase 1 Exit Checklist

| Area | Criterion | Result / evidence |
| --- | --- | --- |
| Repository | Coherent structure | PASS — actual application boundaries |
| Repository | Secrets excluded | PASS — ignored env, source/log scan |
| Repository | Correct gitignore | PASS — explicit ignore verification and generated-cache cleanup |
| Repository | Environment examples | PASS — root/frontend examples |
| Backend | FastAPI starts | PASS — local process and final container |
| Backend | API versioning | PASS — `/api/v1/system` contract |
| Backend | Central configuration | PASS — typed settings tests |
| Backend | MongoDB adapter works | PASS — real MongoDB ping |
| Backend | Neo4j adapter works | PASS — real connectivity/database query |
| Backend | Lifecycle management | PASS — real and boundary cleanup tests; SIGTERM log |
| Backend | Liveness | PASS — healthy and outage HTTP |
| Backend | Real readiness | PASS — actual up/down/recovery HTTP |
| Backend | Structured logging | PASS — actual JSON request/lifecycle logs and formatter assertions |
| Backend | Request IDs | PASS — HTTP headers/error IDs/concurrency tests |
| Backend | Exception handling | PASS — 404/405/422/500/503 behavior tests |
| Backend | Configurable CORS | PASS — environment and allow/reject tests; HTTP header |
| Frontend | React starts | PASS — Vite serves; React mounts in rendering tests |
| Frontend | TypeScript works | PASS — strict project check |
| Frontend | API client boundary | PASS — client tests and live integration |
| Frontend | Displays backend health | PASS — rendering tests + real decoded health |
| Frontend | Loading state | PASS — accessible rendering test |
| Frontend | Failure state | PASS — outage/unreachable rendering and client tests |
| Frontend | Production build | PASS — Vite production output |
| Testing | Backend unit tests | PASS — 50 |
| Testing | Real integration tests | PASS — 6 backend + 1 frontend |
| Testing | Frontend tests | PASS — 18 including live test |
| Testing | Lint | PASS — Ruff/ESLint |
| Testing | Type checks | PASS — Mypy/TypeScript |
| Testing | Production builds | PASS — frontend and backend image |
| Runtime | Frontend reaches backend | PASS — real client and Vite proxy |
| Runtime | Backend reaches MongoDB | PASS — real readiness and integration |
| Runtime | Backend reaches Neo4j | PASS — real readiness and integration |
| Runtime | Graceful degradation | PASS — each/both DB down and outage startup |
| Documentation | Root README accurate | PASS — setup/start/tests/limits documented |
| Documentation | Architecture | PASS — boundaries/data ownership/extensions |
| Documentation | ADR | PASS — ADR-001 |
| Documentation | Startup commands | PASS — executed setup/integration/local/container commands |
| Documentation | Test commands | PASS — executed quality gate and evidence commands |
| Documentation | Troubleshooting | PASS — actual local failure cases covered |

Additional verification: **browser visual QA NOT VERIFIED; hosted CI NOT VERIFIED; Python 3.13/native host variants NOT VERIFIED.** These are separate from the 39 stated engineering criteria.

## 19. Phase 2 Readiness

**Phase 2 can begin on this foundation.** Real Neo4j connectivity and configured-database validation are established without committing to a graph schema. Add the knowledge module, canonical entity/relationship definitions, ingestion validation and appropriate graph repository interfaces with Phase 2 use cases. Preserve the API → application/domain → infrastructure direction and data ownership.

There is no resume processing, graph ingestion, FAISS index, embedding generation, hybrid retrieval, agent orchestration, LLM integration or research evaluation result in Phase 1.

## 20. Exact Commands

Reproduction with normally installed uv, from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/setup-env.ps1
uv sync --project backend --frozen
cd frontend
npm.cmd ci
cd ..
docker compose up -d --wait --wait-timeout 240
```

Separate terminals:

```powershell
cd backend
uv run --frozen python -m app
```

```powershell
cd frontend
npm.cmd run dev
```

Quality and isolated integration:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start-integration.ps1
$env:CP_RUN_INTEGRATION = '1'
$env:TEST_NEO4J_PASSWORD = (Select-String -Path .env -Pattern '^NEO4J_LOCAL_PASSWORD=').Line.Split('=',2)[1]
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1 -Integration
```

The frontend live opt-in additionally requires a reachable backend and Vite. For isolated local backend ports, use the environment/startup instructions in README; then:

```powershell
$env:CP_RUN_FRONTEND_INTEGRATION = '1'
cd frontend
npm.cmd test
cd ..
node scripts/verify-runtime.mjs ready
```

For the isolated container workflow, set `BACKEND_PROXY_TARGET=http://127.0.0.1:8001` in ignored frontend `.env`, restart Vite, and use:

```powershell
docker compose -p careerpilot-integration -f compose.yaml -f compose.test.yaml --profile app up -d --build --wait --wait-timeout 240
$env:CP_RUNTIME_BACKEND = 'http://127.0.0.1:8001'
node scripts/verify-runtime.mjs ready
```

Backend package audit command executed in this workspace:

```powershell
./.tools/uv.exe tool run --from pip-audit pip-audit --path backend/.venv/Lib/site-packages --progress-spinner off --format json
```

This session's uv executable is `./.tools/uv.exe`; from `backend/`, use `../.tools/uv.exe run --frozen ...` if uv is not globally installed. The verified existing virtual environment also supports direct `./.venv/Scripts/python.exe -m ...` commands. `.tools` is intentionally excluded from source control.

Scoped verification teardown:

```powershell
docker compose -p careerpilot-integration -f compose.yaml -f compose.test.yaml --profile app down --volumes
```

Full environment reference, individual check commands, runtime outage scenarios, Docker/local workflows and troubleshooting are maintained in [README.md](README.md).
