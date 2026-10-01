# CareerPilot

**A Multi-Agent Placement Intelligence System Using Knowledge Graph-Enhanced Agentic RAG**

CareerPilot is a placement-preparation and career-mentoring system. Its planned capabilities combine persistent student profiles, resume evidence, career-domain knowledge, graph/vector retrieval, agent orchestration, and evidence-backed preparation workflows. KA-RAG informs the research direction; this repository does not implement the paper or claim its results.

**Current status: Phase 1 implemented and locally verified.** See [PHASE1_REPORT.md](PHASE1_REPORT.md) for exact evidence and verification limits. No Phase 2+ business functionality is implemented.

## Scope and architecture

```text
React + TypeScript
       |
       v
FastAPI (one modular monolith)
       |
Application services / dependency protocols
       |
Infrastructure adapters
       +-- MongoDB: student/application state (future collections)
       +-- Neo4j: canonical career knowledge (future graph schema)
```

Phase 1 includes a status page, versioned system metadata, real liveness/readiness checks, pooled asynchronous database adapters, typed settings, sanitized errors, JSON logs, correlation IDs, tests, Docker development services, and quality checks. Authentication, resume upload, graph ingestion, FAISS, LLM providers, roadmaps, interviews, and scoring are deliberately outside this phase.

Domain modules will be added when their real use cases arrive; there are no empty placeholder modules. See [architecture](docs/architecture/phase1.md), [ADR-001](docs/architecture/ADR-001-modular-monolith.md), and [API conventions](docs/api-contract.md).

## Prerequisites

- Python **3.12 or 3.13** (verified with 3.12.14).
- uv **0.12.21** for reproducible Python dependencies; [official installation](https://docs.astral.sh/uv/getting-started/installation/).
- Node **24 LTS** recommended; supported Node range is `^22.12.0 || ^24.0.0 || >=26.0.0`. Verified with 24.19.0 and npm 11.17.0.
- Docker Desktop with its Linux engine running, or Docker Engine; Compose **2.24.4+** for `!override`.
- PowerShell 5.1+ on Windows, or PowerShell 7 on Linux/macOS for the quality script. Individual commands work without PowerShell.
- Free local ports: development 8000, 5173, 27017, 7687, 7474; isolated integration 27617, 7767, 7744, 8001.

Commands below start from the repository root unless stated otherwise. On Windows use `npm.cmd` if execution policy blocks npm's PowerShell shim.

## Local configuration

```powershell
./scripts/setup-env.ps1
uv sync --project backend --frozen
cd frontend
npm.cmd ci
cd ..
```

The setup script preserves existing configuration and generates a random local Neo4j password into ignored `.env`. Alternatively copy `.env.example` to `.env`, choose a local password (at least eight characters), and put the same value in `CP_NEO4J_PASSWORD` and `NEO4J_LOCAL_PASSWORD`. Copy `frontend/.env.example` to `frontend/.env` if you need overrides.

On Windows hosts that disable scripts, invoke each reviewed project script with a process-only override, for example `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/setup-env.ps1`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start-integration.ps1`, or `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1 -Integration`. These commands do not change the machine's persistent execution policy. Linux/macOS can use `pwsh -File scripts/check.ps1`.

Backend settings use **`CP_`** to avoid machine-wide environment collisions. The root `.env` location is resolved from the configuration module, independently of the working directory. Environment variables override the file. Never place secrets in `VITE_*` values: they are public browser configuration.

| Variable | Purpose / development default |
| --- | --- |
| `CP_APP_NAME` | Fixed identity `CareerPilot`; other names rejected |
| `CP_APP_ENV` | `development`, `test`, or `production` |
| `CP_DEBUG` | `false`; traceback responses always disabled |
| `CP_HOST`, `CP_PORT` | `127.0.0.1`, `8000` for local startup |
| `CP_API_PREFIX` | Fixed `/api/v1` |
| `CP_LOG_LEVEL` | `INFO`; standard uppercase levels |
| `CP_CORS_ORIGINS` | JSON list of explicit origins; local Vite origins by default |
| `CP_MONGODB_URI` | `mongodb://localhost:27017`; secret-wrapped in settings |
| `CP_MONGODB_DATABASE` | `careerpilot_dev` |
| `CP_NEO4J_URI`, `CP_NEO4J_USER` | `bolt://localhost:7687`, `neo4j` |
| `CP_NEO4J_PASSWORD` | Empty until configured; readiness fails honestly |
| `CP_NEO4J_DATABASE` | `neo4j` |
| `CP_DEPENDENCY_TIMEOUT_SECONDS` | `3`; bounded startup, probes, and cleanup |
| `NEO4J_LOCAL_PASSWORD` | Required Compose development credential |
| `MONGODB_PORT`, `NEO4J_BOLT_PORT`, `NEO4J_HTTP_PORT` | Optional published development database ports |
| `VITE_API_BASE_URL` | Empty = same-origin; set public API origin for separate deployments |
| `BACKEND_PROXY_TARGET` | Vite dev proxy only; defaults to `http://127.0.0.1:8000` |
| `CP_VITE_POLLING` | Frontend dev watcher only; `true` enables polling on locked/synchronized filesystems |

Production requires explicit MongoDB URI/database, Neo4j URI/user/password, and CORS origins. Debug must be off and CORS origins must be HTTPS. There are no invented production credentials. Production authentication, TLS termination, database roles and private-resource ownership enforcement remain later deployment work; this local Compose configuration is not a production deployment.

## Database startup

```powershell
docker compose config --quiet
docker compose up -d --wait --wait-timeout 240
docker compose ps
```

This starts MongoDB 8.0 and Neo4j 5.26 Community with named volumes and real health checks. Published ports bind only to loopback. MongoDB is unauthenticated **only in this local development setup**. Neo4j requires your local password. No application collections, graph schema or seed data are created.

## Backend startup

In a separate terminal:

```powershell
cd backend
uv run --frozen python -m app
```

FastAPI serves `http://127.0.0.1:8000`; OpenAPI is at `/openapi.json`, Swagger UI at `/docs`. Use Ctrl+C for graceful shutdown. For automatic reload, use `uv run --frozen uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000`; the normal entry point additionally sanitizes invalid settings diagnostics.

The process starts even if databases are down. Pools are allocated once per lifespan. Startup probes are bounded; readiness probes actual dependencies on every call and recovers when reachable databases return. An absent Neo4j password requires configuration and a restart. No in-memory fallback exists. Shutdown attempts to close both adapters even if one close fails, with bounded cleanup.

## Frontend startup

In another terminal:

```powershell
cd frontend
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. The status interface has loading, ready, dependency outage and unreachable backend states, a manual refresh button, and request IDs. Vite forwards `/health` and `/api` to FastAPI. The production bundle needs either a reverse proxy for those paths or `VITE_API_BASE_URL` set **before building**; Vite preview does not supply the development proxy.

## Docker application workflow

Stop any locally running backend on port 8000 before this workflow:

```powershell
docker compose --profile app up -d --build --wait --wait-timeout 240
docker compose --profile app ps
docker compose --profile app logs backend
docker compose --profile app down
```

The optional backend container runs as a non-root user and serves port 8000. Frontend remains local. Dependencies use `service_started` rather than blocking backend startup on healthy databases, preserving diagnostics during outages. Backend container health reflects readiness. `down` preserves development data; use deliberate volume cleanup only when you intend to discard it.

## Health and API checks

```powershell
curl.exe http://127.0.0.1:8000/health/live
curl.exe http://127.0.0.1:8000/health/ready
curl.exe http://127.0.0.1:8000/api/v1/system
```

- `/health/live`: 200 `{"status":"alive"}`; process health, independent of databases.
- `/health/ready`: real concurrent MongoDB ping and Neo4j handshake plus configured-database query. 200 with both `up`; 503 with failed dependencies `down` and a structured error. This represents infrastructure readiness, not placement-readiness scoring.
- `/api/v1/system`: identity, version, and implemented phase. No duplicate versioned health route.
- All requests receive `X-Request-ID`; supplied IDs are accepted only if 1–64 ASCII letters/digits/underscores/dashes. Invalid IDs are replaced. Errors include the same ID.

## Tests and quality checks

```powershell
./scripts/check.ps1
```

The gate stops on the first failing command. It runs backend format/lint/strict typing/unit tests, then frontend format/lint/strict typing/tests/production build. External database tests are separate and opt-in; no skipped integration test is treated as a pass.

Individual backend commands, from `backend/`:

```powershell
uv run --frozen ruff format --check app tests
uv run --frozen ruff check app tests
uv run --frozen mypy
uv run --frozen pytest -q -m "not integration"
uv run --frozen pytest -q
```

Frontend commands, from `frontend/`:

```powershell
npm.cmd run lint
npm.cmd run format:check
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npm.cmd audit
```

### Real database integration

```powershell
./scripts/start-integration.ps1
```

This starts project `careerpilot-integration` on dedicated ports and runs the real tests with a separately named MongoDB test database. The script intentionally leaves containers running for inspection. Tests reject non-loopback targets and normal database ports. They only ping/read `RETURN 1`; there are no application writes. Neo4j Community has one database: isolation uses a separate container and volume, not a shared production database.

Equivalent commands:

```powershell
docker compose -p careerpilot-integration -f compose.yaml -f compose.test.yaml up -d --wait --wait-timeout 240
$env:CP_RUN_INTEGRATION = '1'
# Assign your generated local test-service password without pasting it into tracked files.
$env:TEST_NEO4J_PASSWORD = (Select-String -Path .env -Pattern '^NEO4J_LOCAL_PASSWORD=').Line.Split('=',2)[1]
cd backend
uv run --frozen pytest -q -m integration
cd ..
./scripts/check.ps1 -Integration
```

To run the frontend client against the real chain, first start the backend against isolated ports in its own terminal:

```powershell
$env:CP_MONGODB_URI = 'mongodb://127.0.0.1:27617'
$env:CP_MONGODB_DATABASE = 'careerpilot_test'
$env:CP_NEO4J_URI = 'bolt://127.0.0.1:7767'
cd backend
uv run --frozen python -m app
```

With Vite also running, from a separate terminal:

```powershell
node scripts/verify-runtime.mjs ready
cd frontend
$env:CP_RUN_FRONTEND_INTEGRATION = '1'
npm.cmd test
cd ..
```

`verify-runtime.mjs` checks live HTTP, readiness, request IDs, CORS, OpenAPI, frontend serving and proxy responses. Test real outages using only the isolated project:

```powershell
docker compose -p careerpilot-integration -f compose.yaml -f compose.test.yaml stop mongodb
node scripts/verify-runtime.mjs mongo-down
docker compose -p careerpilot-integration -f compose.yaml -f compose.test.yaml up -d --wait --wait-timeout 240
# Repeat with stop neo4j and scenario neo4j-down, or stop both and scenario both-down.
```

Cleanup the isolated project and its disposable test volumes when finished:

```powershell
docker compose -p careerpilot-integration -f compose.yaml -f compose.test.yaml --profile app down --volumes
```

CI contains the same unit gate and real isolated integration workflow. GitHub execution is not verified locally; no commit, push or deployment was performed.

## Troubleshooting

| Symptom | Check / action |
| --- | --- |
| Docker pipe/daemon error | Start Docker Desktop and wait for the Linux engine; run `docker info` |
| MongoDB down | Check URI, selected database, container health and port; liveness still works |
| Neo4j down | Check URI/user/password/database; local backend and Compose passwords must match |
| Password changed but Neo4j rejects it | Existing named volume retains original credentials; update them intentionally or use a fresh disposable test project |
| Backend startup says invalid configuration | Check `CP_` names, JSON CORS list, URI schemes, port and production policy; raw inputs are suppressed |
| Frontend cannot reach backend | Verify `/health/live`, proxy target or public API origin; an unreachable backend leaves database status unknown |
| Cross-origin requests fail | Allow the exact frontend scheme/hostname/port; wildcard origins and credentials are not enabled |
| Port occupied | Stop the conflicting process or change configured ports and the frontend proxy target together |
| Windows `spawn EPERM` | Run tests/builds in a normal permitted terminal; sandbox restrictions can block Vite child processes |
| OneDrive watcher `EBUSY` | Set `CP_VITE_POLLING=true` in `frontend/.env` and restart Vite; initialize env files before starting Vite |
| Python command opens Microsoft Store | Install Python or let uv provision 3.12; use `uv run` from the backend directory |
| Integration tests skipped | Set the explicit opt-in and start isolated infrastructure; skip is not connectivity evidence |

## Implementation references

The adapters use the supported asynchronous driver APIs and lifespan mechanisms described in [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/), [PyMongo client lifecycle](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/connect/mongoclient/), and [Neo4j async driver API](https://neo4j.com/docs/api/python-driver/current/async_api.html).
