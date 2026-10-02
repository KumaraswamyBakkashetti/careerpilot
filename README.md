# CareerPilot

**A Multi-Agent Placement Intelligence System Using Knowledge Graph-Enhanced Agentic RAG**

CareerPilot is a placement-preparation and career-mentoring system. Its planned capabilities combine persistent student profiles, resume evidence, career-domain knowledge, graph/vector retrieval, agent orchestration, and evidence-backed preparation workflows. KA-RAG informs the research direction; this repository does not implement the paper or claim its results.

**Current status: Phase 7 frontend experience implemented and locally verified.** CareerPilot includes grounded company preparation, text mock interviews, practice-evidence feedback, deterministic readiness snapshots, and a bounded specialist orchestrator inside a persistent evidence-led workspace. The only company is explicitly synthetic; readiness is not a hiring probability. See [PHASE7_REPORT.md](PHASE7_REPORT.md) for frontend evidence and limits, and [PHASE6_REPORT.md](PHASE6_REPORT.md) for domain verification.

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
       +-- MongoDB: accounts, profiles, resumes, evidence, gap snapshots
       +-- private storage: original PDF/DOCX files
       +-- Neo4j: canonical career knowledge and role requirements
       +-- FAISS: rebuildable normalized resource-chunk vectors
       +-- MongoDB: owner-scoped retrieval traces
       +-- Groq via LLMGateway: grounded structured synthesis only
       +-- MongoDB: owner-scoped roadmaps and generation runs
       +-- MongoDB: preparations, interviews, practice evidence, readiness, orchestration
```

Phase 6 retains every earlier boundary. Neo4j answers structural questions, FAISS finds semantic passages, MongoDB owns private mutable history, deterministic rules calculate readiness, and Groq generates only validated prose within specialist contracts. There are no autonomous agent loops, web search, provider tools, coding execution, voice/video analysis, placement prediction, or student-resume embeddings.

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

The setup script preserves existing configuration and generates a random local Neo4j password and 32-byte JWT signing secret into ignored `.env`. Alternatively copy `.env.example` to `.env`, set both secrets, and put the same Neo4j password in `CP_NEO4J_PASSWORD` and `NEO4J_LOCAL_PASSWORD`. Copy `frontend/.env.example` to `frontend/.env` if you need overrides.

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
| `CP_JWT_SECRET`, `CP_JWT_TTL_MINUTES` | Required signing secret; 60-minute local token lifetime |
| `CP_RESUME_MAX_BYTES` | 5 MiB upload limit |
| `CP_RESUME_MAX_PAGES`, `CP_RESUME_MAX_TEXT_CHARS` | 20 pages and 200,000 extracted characters |
| `CP_RESUME_STORAGE_ROOT` | Private local storage; Docker uses a named volume |
| `CP_RETRIEVAL_INDEX_ROOT` | Private derived FAISS artifact root; never web-served |
| `CP_RETRIEVAL_EMBEDDING_MODEL`, `CP_RETRIEVAL_EMBEDDING_REVISION` | Local model ID and immutable revision |
| `CP_RETRIEVAL_EMBEDDING_DIMENSION` | Required manifest/vector dimension; 384 |
| `CP_RETRIEVAL_CHUNK_SIZE`, `CP_RETRIEVAL_CHUNK_OVERLAP` | Versioned deterministic chunk configuration; 420/40 |
| `CP_RETRIEVAL_TOP_K`, `CP_RETRIEVAL_MAX_TOP_K` | Default and hard retrieval limits; 3/20 |
| `NEO4J_LOCAL_PASSWORD` | Required Compose development credential |
| `MONGODB_PORT`, `NEO4J_BOLT_PORT`, `NEO4J_HTTP_PORT` | Optional published development database ports |
| `VITE_API_BASE_URL` | Empty = same-origin; set public API origin for separate deployments |
| `BACKEND_PROXY_TARGET` | Vite dev proxy only; defaults to `http://127.0.0.1:8000` |
| `CP_VITE_POLLING` | Frontend dev watcher only; `true` enables polling on locked/synchronized filesystems |

Production requires explicit MongoDB URI/database, Neo4j URI/user/password, JWT secret, private storage root, and HTTPS CORS origins. Debug must be off. TLS termination, database credentials/roles, rate limiting, token revocation, backup, malware scanning, and durable object storage remain deployment work; this local Compose configuration is not a production deployment.

## Database startup

```powershell
docker compose config --quiet
docker compose up -d --wait --wait-timeout 240
docker compose ps
```

This starts MongoDB 8.0 and Neo4j 5.26 Community with named volumes and real health checks. Published ports bind only to loopback. MongoDB is unauthenticated **only in this local development setup**. Neo4j requires your local password. Compose does not mutate the graph automatically; run the explicit schema/ingestion commands below.

## Backend startup

In a separate terminal:

```powershell
cd backend
uv run --frozen python -m app
```

FastAPI serves `http://127.0.0.1:8000`; OpenAPI is at `/openapi.json`, Swagger UI at `/docs`. Use Ctrl+C for graceful shutdown. For automatic reload, use `uv run --frozen uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000`; the normal entry point additionally sanitizes invalid settings diagnostics.

The process starts even if databases are down. Pools are allocated once per lifespan. Startup probes are bounded; readiness probes actual dependencies on every call and recovers when reachable databases return. An absent Neo4j password requires configuration and a restart. No in-memory fallback exists. Shutdown attempts to close both adapters even if one close fails, with bounded cleanup.

## Career knowledge setup

The seed is [backend/knowledge_data/seed.json](backend/knowledge_data/seed.json), version `careerpilot-knowledge-v1`. Its six source notes are hashed and every relationship cites an exact assertion locator. Validate before opening Neo4j, then ingest through the local CLI:

```powershell
cd backend
uv run --frozen python -m app.modules.knowledge.cli validate
uv run --frozen python -m app.modules.knowledge.cli schema
uv run --frozen python -m app.modules.knowledge.cli ingest --accept-curated
uv run --frozen python -m app.modules.knowledge.cli inspect
uv run --frozen python -m app.modules.knowledge.cli profile
```

`--accept-curated` records the operator's explicit acceptance of the reviewed learning profiles and synthetic demonstration. Ingestion is a single Neo4j transaction, uses dataset ownership, rejects same-version content changes and version downgrades, and prunes only records owned by this dataset. Running it repeatedly does not add nodes or relationships. Cypher lives only in the infrastructure adapter; no HTTP write or arbitrary-Cypher endpoint exists.

Read APIs under `/api/v1/knowledge` include roles, role skills, skill resources/topics, assertion provenance, company roles/context, and company-role skills. Lists use stable name/ID order, `limit` 1–100, and `offset` 0–10000. Examples:

```powershell
curl.exe http://127.0.0.1:8000/api/v1/knowledge/roles
curl.exe http://127.0.0.1:8000/api/v1/knowledge/roles/role_backend_developer/skills
curl.exe http://127.0.0.1:8000/api/v1/knowledge/skills/skill_python/resources
```

The frontend explorer loads these endpoints; it has separate loading, empty, missing, graph-outage, and backend-outage states. If it reports knowledge unavailable, check `/health/ready`, container health, seed ingestion, and then `cli inspect`. Details are in [knowledge graph architecture](docs/architecture/knowledge-graph.md) and [dataset notes](docs/knowledge-dataset.md).

## Private student evidence

Registration and login return a short-lived bearer token. Private routes derive the owner from that token; they never accept a `student_id` parameter. A minimal API sequence is:

```text
POST   /api/v1/auth/register
POST   /api/v1/auth/token
GET    /api/v1/student/profile
PUT    /api/v1/student/profile
POST   /api/v1/student/resumes
GET    /api/v1/student/resumes
POST   /api/v1/student/resumes/{resume_id}/process
DELETE /api/v1/student/resumes/{resume_id}
GET    /api/v1/student/resumes/{resume_id}/evidence
GET    /api/v1/student/evidence
PUT    /api/v1/student/evidence/{evidence_id}
POST   /api/v1/student/gap-analyses
GET    /api/v1/student/gap-analyses/{run_id}
```

Uploads use multipart field `file`. Matching PDF and DOCX signatures, MIME types, extensions, parser integrity, and configured limits are required. Files are stored under generated keys. An identical upload for the same student reuses its existing record; different uploads create immutable versions and only the newest is active.

Extraction is synchronous and deterministic. PDF and DOCX text retain useful line and section context; image-only PDFs require OCR and fail explicitly because OCR is outside Phase 3. Exact canonical names and curated aliases normalize through live Neo4j reads. Unknown mentions remain unresolved until rejected or corrected to a backend-validated canonical skill. Gap results use direct evidence only and label requirements `SUPPORTED`, `PARTIALLY_SUPPORTED`, or `UNVERIFIED`; they never infer proficiency.

Deleting a resume removes the private file, processing run, and derived evidence and tombstones its metadata. Historical gap snapshots remain for audit, without restoring deleted evidence text. Full account deletion is not implemented. The complete design is in [student evidence architecture](docs/architecture/student-evidence.md) and [ADR-005](docs/architecture/ADR-005-student-evidence-boundary.md).

## Hybrid retrieval setup

Build the derived index after installing backend dependencies and whenever the canonical corpus, embedding revision, dimension, or chunking configuration changes:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.modules.retrieval.cli build
```

For the optional Docker backend, populate its named index/model volumes once with the same controlled CLI before starting the app profile:

```powershell
docker compose --profile app run --rm backend python -m app.modules.retrieval.cli build
docker compose --profile app up -d --wait
```

The selected v1 artifact contains 4 canonical resources and 21 chunks in an integrity-checked normalized-cosine `IndexFlatIP`. The API loads it only when its manifest matches the current model revision, dimension, corpus hash and chunking configuration. A missing, corrupt or stale index fails explicitly; it is never silently searched. Builds stage a new artifact and atomically switch the active pointer. There is no public rebuild endpoint.

Authenticated retrieval routes provide role requirements, skill passages, gap evidence and owner-filtered traces. In the student workspace, run a gap analysis and select **Retrieve evidence** to inspect graph evidence separately from learning passages and their sources.

Run the controlled experiment (downloads public model weights on first use):

```powershell
cd ..
.\backend\.venv\Scripts\python.exe scripts\evaluate-phase4.py
```

The labelled dataset is [backend/retrieval_data/evaluation-v1.json](backend/retrieval_data/evaluation-v1.json); generated results are [JSON](docs/evaluation/phase4-retrieval-results.json) and [Markdown](docs/evaluation/phase4-retrieval-results.md). Full design and failure semantics are in [hybrid retrieval architecture](docs/architecture/hybrid-retrieval.md) and [ADR-006](docs/architecture/ADR-006-hybrid-retrieval-baseline.md).

## Grounded roadmap generation

Put the Groq secret in the untracked root `.env`; never expose it through Vite:

```env
GROQ_API_KEY=gsk_your_key
```

The model and reasoning level are configuration-driven. Optional overrides use `CP_GROQ_MODEL`, `CP_GROQ_REASONING_EFFORT`, `CP_GROQ_TIMEOUT_SECONDS`, and `CP_GROQ_MAX_RETRIES`.

From Command Prompt, verify the live project catalog and strict structured output:

```bat
cd /d C:\Users\kumar\Downloads\CareerPilot\CareerPilot\backend
.venv\Scripts\python.exe -m app.modules.llm.cli --smoke
```

In the student workspace, run a gap analysis and select **Generate grounded learning roadmap**. The UI separates canonical requirements, student evidence status, retrieved resources, and generated synthesis. Partial corpus coverage names omitted skills instead of inventing recommendations.

Run the controlled live evaluation only when quota permits:

```bat
cd /d C:\Users\kumar\Downloads\CareerPilot\CareerPilot\backend
.venv\Scripts\python.exe ..\scripts\evaluate-phase5.py --compare
```

Generated evaluation results are [JSON](docs/evaluation/phase5-generation-results.json) and [Markdown](docs/evaluation/phase5-generation-results.md). Architecture and policy are in [grounded LLM generation](docs/architecture/llm-generation.md) and [ADR-007](docs/architecture/ADR-007-grounded-llm-generation.md).

## Frontend startup

In another terminal:

```powershell
cd frontend
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. Create a private workspace or sign in, upload a PDF/DOCX, review each extracted mention, choose a canonical role, and run gap analysis. Tokens stay in React memory and are cleared on refresh/sign-out. The page also retains the knowledge explorer and service diagnostics. Vite forwards `/health` and `/api` to FastAPI. The production bundle needs either a reverse proxy for those paths or `VITE_API_BASE_URL` set **before building**.

The Phase 7 shell provides direct hash navigation for the supported workflow surfaces: `#overview`, `#evidence`, `#gap`, `#roadmap`, `#practice`, and `#readiness`. The visual language, semantic evidence tokens, responsive behavior, and reduced-motion policy are documented in [the frontend design system](docs/frontend/design-system.md) and [frontend architecture](docs/architecture/frontend.md).

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

This starts project `careerpilot-integration` on dedicated ports and runs the real tests with a separately named MongoDB test database. The script intentionally leaves containers running for inspection. Tests reject non-loopback targets and normal database ports. Phase 3 tests write disposable accounts, resumes, evidence, and gap snapshots to that isolated MongoDB and idempotently seed the isolated Neo4j graph. Neo4j Community has one database, so isolation uses a separate container and volume rather than a shared production database.

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

The adapters use the supported asynchronous driver APIs and lifespan mechanisms described in [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/), [PyMongo client lifecycle](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/connect/mongoclient/), and [Neo4j async driver API](https://neo4j.com/docs/api/python-driver/current/async_api.html). Phase 5 provider behavior follows Groq's live Models API and strict Structured Outputs documentation; runtime discovery remains authoritative for project access.
