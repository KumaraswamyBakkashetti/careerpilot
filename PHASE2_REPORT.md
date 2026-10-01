# CareerPilot Phase 2 Implementation Report

## 1. Executive Summary

Phase 2 establishes a small, reproducible canonical career knowledge graph. FastAPI reads typed Neo4j entities and relationships through a repository boundary, every relationship carries retrievable source evidence, a controlled CLI validates and atomically ingests a versioned seed, and React displays real role-to-skill results with importance and provenance.

## 2. Baseline

Before modification, the Phase 1 gate passed: 56 backend tests and 18 frontend tests, including the opt-in database/client tests (74 passed, 0 failed, 0 skipped). MongoDB/Neo4j lifecycle behavior, sanitized errors, request IDs, Docker, and the React status page were retained. A hash inventory was written to the ignored `artifacts/phase2/baseline-files.json` before source edits.

## 3. Architecture

The implemented path is React → versioned FastAPI knowledge routes → `KnowledgeService` → `KnowledgeRepository` protocol → `Neo4jKnowledgeRepository` → Neo4j. Domain models contain identity and graph invariants. Cypher is confined to the infrastructure adapter. Neo4j owns canonical career knowledge; MongoDB remains reserved for student/application state.

## 4. Domain Model

The exact canonical node types are Skill, Role, Company, CompanyRole, Resource, and InterviewTopic. Sources and dataset manifests are supporting records rather than domain entities. Strict payloads are persisted and validated again on retrieval. Resource requires an HTTPS URL/content reference; only Skill supports normalized aliases/category; synthetic status is explicit.

## 5. Relationship Model

The exact types are OFFERS_ROLE (Company → CompanyRole), BASED_ON (CompanyRole → Role), REQUIRES_SKILL (Role/CompanyRole → Skill), TEACHES_SKILL (Resource → Skill), COVERS_TOPIC (Resource → InterviewTopic), and ASSESSES_SKILL (InterviewTopic → Skill). Endpoint direction is validated before writes and during graph inspection.

## 6. Provenance Design

The chosen hybrid uses direct canonical relationships with full assertion evidence in the relationship payload and shared `KnowledgeSource` records for source metadata. API DTOs combine both. Evidence includes source title/type/URI/publisher, known publication time, collection time, hash, dataset version, evidence text, locator, method, and validation time. This preserves simple traversal without duplicating shared source metadata. There are no invented confidence weights.

## 7. Stable Identity Strategy

Human-readable lowercase IDs have kind prefixes. A relationship ID is SHA-256 of its source/type/target triple, truncated to 32 hex characters. Name changes do not change identity. Exact skill aliases use NFKC, case folding, and whitespace collapse; collision detection rejects ambiguity. Ingestion rejects cross-owner IDs and entity-kind changes.

## 8. Dataset

`careerpilot-knowledge-v1` contains 36 canonical entities: Skill 20, Role 5, InterviewTopic 5, Resource 4, Company 1, CompanyRole 1. It contains 67 relationships: REQUIRES_SKILL 42, ASSESSES_SKILL 10, TEACHES_SKILL 9, COVERS_TOPIC 4, OFFERS_ROLE 1, BASED_ON 1. Six sources comprise two project notes and four official-documentation observation notes. The only company is `CareerPilot Demo Labs`, explicitly fictional.

## 9. Ingestion

`python -m app.modules.knowledge.cli ingest --accept-curated` validates the complete local snapshot before database access, ensures constraints, then runs owned source/entity/relationship merge and pruning in one managed Neo4j transaction. No HTTP graph-write endpoint exists. Explicit acceptance acknowledges the project-authored profiles and synthetic demonstration.

## 10. Validation

Validation covers strict fields, ID syntax/prefixes, unique IDs, normalized entity and alias collisions, source references, HTTPS/URN policy, timestamps, snapshot confinement/hash, evidence locator/text presence, allowed endpoints/directions, duplicate logical triples, importance semantics, provenance methods, synthetic markers, and CompanyRole cardinality. Malformed seeds never open Neo4j.

## 11. Idempotency

Real Neo4j integration ingested v1, captured counts, ingested it again, and compared counts plus full inspection. Counts remained 36 entities, 67 relationships, and 6 sources. Same-version changed content and version downgrades are rejected. The mutable manifest lock is concurrency metadata and does not create canonical records.

## 12. Neo4j Schema

Fifteen uniqueness constraints exist: six canonical label IDs, `KnowledgeEntity`, `KnowledgeSource`, `KnowledgeDataset`, and six relationship-type IDs. Their backing indexes cover stable-ID entry points. No redundant secondary index was added for this small seed. `SHOW CONSTRAINTS` returned all 15 during the real integration test.

## 13. Repository Layer

The application protocol exposes list/detail, related entities with evidence, provenance, and company context. The Neo4j implementation maps every persisted JSON payload into strict models and emits `KNOWLEDGE_INCONSISTENT` if stored data violates the contract. Reads have bounded driver timeouts, deterministic order, and parameterized data values; the only interpolated tokens are closed-vocabulary labels/types.

## 14. APIs

Implemented endpoints are roles list/search/detail/skills; skill detail/resources/topics; resource topics; assertion provenance; company-role list/context/skills. They are under `/api/v1/knowledge`. List limits are 1–100 and offsets 0–10000. Missing knowledge returns 404, invalid requests 422, Neo4j unavailability 503, and inconsistent persisted data a sanitized 500.

## 15. Frontend

The React page retains live foundation status and adds a role selector backed entirely by APIs. Selecting a role loads Neo4j skills, importance, dataset version, and source links/indicators. It separately handles role loading, empty role data, deleted roles, empty relationships, Neo4j outage, and backend/network failure. There are no hardcoded role or skill arrays.

## 16. Tests

Final local commands/results:

- Backend full suite with isolated services: 72 passed, 0 failed, 0 skipped.
- Frontend full suite with live integration enabled: 24 passed, 0 failed, 0 skipped.
- Backend non-integration development gate: 62 passed; its 10 integration tests are deselected by design, not reported as passed by that command.
- Phase 1 baseline: 56 backend + 18 frontend = 74 passed, 0 failed, 0 skipped.

Tests include identity and alias logic, seed mutation failures, snapshot tampering, DTO/service/API behavior, bounds/errors, real constraints/counts/queries/provenance, repeat ingestion, rollback, real FastAPI graph access, frontend decoders/states, and the live frontend-client path.

## 17. Data Quality

The canonical seed loaded with 36 unique entity IDs, 67 unique assertion IDs/triples, no alias/name collision, no dangling endpoint/source, no missing evidence, valid importance values, and exact CompanyRole ownership/base links. `cli inspect` reconstructed the stored dataset and passed label, property, direction, type, provenance, content-hash, and disconnected-node checks.

## 18. Runtime Verification

Docker Engine 29.7.2 ran MongoDB 8.0.32, Neo4j 5.26.31, and the rebuilt non-root backend container. The backend image copied the seed, installed from the frozen lock, became healthy, and returned live graph API data. Schema, ingestion, inspection, and PROFILE were executed against port 7767.

## 19. End-to-End Verification

With Vite on 5173 and the rebuilt FastAPI container on 8001, the real frontend TypeScript client traversed Vite → FastAPI → service/repository → Neo4j. It observed five roles; Backend Developer had ten skills; Python was CORE; and its source title was `CareerPilot v1 curated learning profiles`. Both live client integration tests passed.

## 20. Outage Testing

The isolated Neo4j container was actually stopped. FastAPI liveness stayed 200, readiness returned 503, and `/api/v1/knowledge/roles` returned sanitized 503 `DEPENDENCY_UNAVAILABLE` without URI/password content. Neo4j was restarted and reached healthy; without restarting FastAPI, readiness and the knowledge endpoint both returned 200.

## 21. Ingestion Failure Testing

Unit/data tests rejected duplicate IDs, unknown targets, missing importance, missing provenance, wrong relationship type/direction, unsafe source URI, and tampered source content. The real integration test induced an exception after all writes inside a managed transaction; the manifest lock remained unchanged and full graph inspection still passed, demonstrating rollback rather than partial persistence.

## 22. Performance Baseline

Twenty warm local HTTP samples per operation through the Docker backend produced median/p95 milliseconds: roles 22.06/30.64; Backend Developer skills 35.87/56.43; Python resources 22.28/31.65; assertion provenance 21.41/29.85. This Windows/Docker/loopback baseline is for regression comparison, not production capacity.

PROFILE showed a Role label scan for the five-row list, index-backed node entry for role-skill and skill-resource traversal, and `DirectedRelationshipUniqueIndexSeek` for provenance. All traversals are one hop, bounded, and had no Cartesian product.

## 23. Security Review

All input values are Cypher parameters; dynamic labels/types come only from closed enumerations. There is no arbitrary query or public write API. Pagination and seed size are bounded, driver errors are sanitized, source logs exclude raw data, and the seed contains no credentials. A repository scan found only the intentional invalid-configuration test URI. `npm audit --omit=dev` found 0 vulnerabilities; `pip-audit` found no known vulnerabilities.

## 24. Code Quality

Ruff formatting/checks passed, mypy strict passed for all 24 backend application files, ESLint passed with zero warnings, TypeScript build checking passed, Prettier passed, Vitest passed, and Vite production build succeeded (33 modules, 232.62 kB JS / 72.74 kB gzip). Backend Docker build and health passed. `git diff --check` reported no whitespace error.

## 25. Files Added/Modified

Added the knowledge domain/service/repository/routes/CLI, Neo4j repository/writer, canonical seed and notes, backend unit/integration tests, typed frontend client/explorer/tests, graph architecture, three ADRs, dataset documentation, and this report. Modified composition, errors/log fields, metadata/version, Docker packaging, README, lock metadata, status UI, styles, and integration tests. User file `run.txt` was preserved.

## 26. Known Limitations

The role profiles are project curation rather than independently reviewed labor-market research. Resources are introductory and coverage is intentionally narrow. Search is exact substring/normalized alias infrastructure, not full text or fuzzy search. Pagination returns no total count. Community Neo4j cannot use enterprise property-existence constraints, so strict ingestion and inspection enforce completeness. The fictional company is demonstration-only.

## 27. Technical Debt

A future reviewed dataset version should add named human reviewer/sign-off metadata and broader independent career sources. If data volume grows, role search needs a measured full-text/index strategy and cursor pagination. Hosted CI was not observed in this local run, although its local commands pass. Automated outage orchestration currently lives in verification procedure rather than a stable test fixture because it controls containers.

## 28. Phase 2 Exit Checklist

Architecture: PASS — Neo4j ownership, MongoDB student boundary, modular-monolith layers.  
Schema: PASS — six node types, documented semantics, stable IDs, 15 real constraints/indexes.  
Provenance: PASS — every relationship traceable; metadata/versioning; no confidence fabrication.  
Dataset: PASS — curated versioned validated seed; real/synthetic distinction; no real-company claim.  
Ingestion: PASS — reproducible, idempotent, duplicate/reference/malformed rejection, atomic rollback.  
Queries: PASS — roles, skills, resources, topics, provenance, and company context queried in real Neo4j.  
API: PASS — typed/bounded responses, correct statuses, parameters, no arbitrary Cypher/write surface.  
Frontend: PASS — real roles/skills/provenance and loading/error/empty handling.  
Tests: PASS — unit, data quality, API, frontend, and 10 real database integration tests; required final runs had zero skips.  
Quality: PASS — formatting, lint, typing, production build, and backend Docker build.  
Runtime: PASS — real graph, frontend-client end to end, repeated ingest, actual outage and recovery.  
Documentation: PASS — README, graph document, ADRs, dataset document, and report.

Every applicable Phase 2 exit criterion passed in the stated local environment. Hosted CI execution is outside this local verification and is not claimed.

## 29. Phase 3 Readiness

Yes, student/resume intelligence can begin behind the existing ownership boundary. Phase 3 should store personal evidence in MongoDB, reference canonical graph IDs, and keep inferred candidate assertions outside canonical Neo4j until an explicit source/normalization/validation/publication boundary approves them.

## 30. Reproduction Commands

```powershell
docker compose -p careerpilot-integration -f compose.yaml -f compose.test.yaml --profile app up -d --build --wait --wait-timeout 180
$taskConfig = Get-Content .env -Raw
$env:TEST_NEO4J_PASSWORD = [regex]::Match($taskConfig,'(?m)^NEO4J_LOCAL_PASSWORD=(.+)$').Groups[1].Value.Trim()
$env:CP_RUN_INTEGRATION = '1'
cd backend
..\.tools\uv.exe sync --frozen
.\.venv\Scripts\python.exe -m app.modules.knowledge.cli validate
.\.venv\Scripts\pytest.exe
cd ..\frontend
$env:CP_RUN_FRONTEND_INTEGRATION = '1'
npm.cmd ci
npm.cmd run check
```

For ordinary development, start databases, run validate/schema/ingest once with the commands in README, start FastAPI from `backend`, then run `npm.cmd run dev` from `frontend`.
