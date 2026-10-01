# CareerPilot Phase 3 Implementation Report

Verification date: 2026-10-01  
Scope: private student profiles, resume evidence, canonical normalization, confirmation, versioning, and deterministic gap analysis

## 1. Executive Summary

Phase 3 implements a complete evidence-centered student backend and focused React workflow. A signed identity owns every private query. Actual PDF and DOCX files pass bounded validation, remain in private storage, and produce deterministic, section-aware candidate evidence. Neo4j supplies canonical skills and role requirements; MongoDB owns mutable private state. Students confirm, reject, or correct evidence before a versioned rule table compares it with a canonical role.

No LLM, embedding, vector store, inferred skill relationship, readiness score, or proficiency score is present.

## 2. Phase 2 Baseline

The repository inspection found the Phase 1 platform and Phase 2 knowledge implementation in the working tree. Before Phase 3 work, the actual local gate produced 62 backend unit passes with 10 integration tests deselected; the isolated database suite produced 10 integration passes. The frontend produced 22 passes and 2 opt-in skips, and its production build passed. These differ in presentation from the prompt's reported aggregate but total the same 72 backend and 24 frontend tests when opt-in suites are included.

## 3. Architecture Implemented

```text
React StudentWorkspace
  -> FastAPI StudentService
     -> Argon2 account + HS256 JWT identity
     -> ResumeStorage -> private local/Docker volume
     -> deterministic PDF/DOCX extraction
     -> read-only Neo4j canonical Skill/Role queries
     -> MongoDB profiles/resumes/runs/evidence/gap snapshots
```

Infrastructure adapters stay behind repository/storage protocols. MongoDB and Neo4j drivers do not leak into domain models. See [student-evidence.md](docs/architecture/student-evidence.md) and [ADR-005](docs/architecture/ADR-005-student-evidence-boundary.md).

## 4. Student Profile Model

`StudentProfile` contains only opaque student ID, display name, optional canonical target role ID, timestamps, and monotonically incremented version. No demographic or speculative fields were added.

## 5. Authentication/Authorization

Passwords use pwdlib's recommended Argon2 hasher. JWTs use HS256, fixed issuer/audience, signed subject, issued/expiry timestamps, and a configurable 5-1440 minute TTL (60 locally). Production rejects missing or shorter-than-32-character secrets.

Every private endpoint derives `student_id` from the bearer JWT. MongoDB queries include that ID alongside the resource ID. Cross-owner resume, evidence mutation, and gap retrieval return owner-scoped not-found responses. Browser credentials are omitted and the frontend token stays in memory.

## 6. Resume Model

Metadata includes opaque resume/owner IDs, sanitized original filename, MIME type, size, SHA-256 hash, internal storage key, lifecycle status, immutable student version, active flag, parser version, and timestamps. API views remove owner and storage key.

## 7. File Storage

`LocalResumeStorage` provides initialize, save, read, exists, delete, and safe path resolution below one configured private root. Generated `resume_<uuid>.pdf|docx` keys use exclusive creation. Docker mounts a named volume at `/app/private/resumes` and runs the backend as UID 10001. No static route or download URL exposes files.

## 8. Upload Security

The API reads at most `max_bytes + 1`; the default is 5 MiB. It rejects empty, oversized, traversal/control-character filename, unsupported extension, mismatched MIME, mismatched signature, corrupt PDF, corrupt DOCX, and unsafe DOCX archives. DOCX checks bound archive members, expanded bytes, and compression ratio. PDF extraction bounds pages and output characters. Error messages omit parser internals and content.

## 9. Resume Processing Pipeline

Implemented states are `STORED -> EXTRACTING_TEXT -> EXTRACTING_STRUCTURE -> NORMALIZING_SKILLS -> AWAITING_CONFIRMATION|COMPLETED`, plus `TEXT_EXTRACTION_FAILED`, `NORMALIZATION_FAILED`, and `DELETED`. A stable processing ID binds resume and parser version. Each stage is persisted.

## 10. Text Extraction

`pypdf` parses actual PDFs and `python-docx` parses actual DOCX packages. Text normalization preserves lines, bounds output, and removes only unusable control/blank noise. Image-only or otherwise textless PDFs fail explicitly with `RESUME_EXTRACTION_FAILED`; OCR is not implemented.

## 11. Structured Extraction

The smallest Phase 3 structure is implemented: section, raw mention, bounded evidence context, extraction method, and character position used for stable identity. Recognized headings cover skills, projects, experience, education, certifications, and other. Education/employment ATS schemas were intentionally omitted because gap analysis does not consume them.

## 12. Skill Normalization

The parser matches case-insensitive canonical names first, then a small explicit alias table such as Postgres to PostgreSQL. It scans canonical terms conservatively in contextual lines and treats unrecognized skills-section tokens as unresolved. It does not equate Java/JavaScript, SQL/MySQL, React/React Native, C/C++, or related graph concepts.

## 13. Canonical Neo4j Integration

Normalization lists the live Phase 2 `Skill` registry. Corrections call canonical `Skill` lookup. Target-role updates call canonical `Role` lookup. Gap analysis calls the seeded `REQUIRES_SKILL` traversal and carries assertion IDs, importance, and dataset version. Resume processing performs no Neo4j mutation.

## 14. SkillEvidence Model

Evidence stores opaque ID, owner, resume, raw text, section, bounded evidence text, optional canonical skill ID/name, `EXACT|ALIAS|UNRESOLVED`, `DETERMINISTIC_ALIAS_V1`, `EXTRACTED|CONFIRMED|REJECTED`, and observation/create/update timestamps. It records evidence, not ability or proficiency.

## 15. Confirmation Workflow

The React workspace displays canonical name or raw unresolved text, section, normalization and verification states, and bounded context. Students may confirm, reject, or select a canonical correction. The backend validates every confirmed/corrected skill against Neo4j. A resume becomes `COMPLETED` only when all evidence has a decision.

## 16. Resume Versioning

A per-student atomic sequence creates versions. A new distinct resume becomes active and prior versions become inactive without deleting their evidence. An identical SHA-256 for the same student returns the existing record with `duplicate=true`. Same-parser retry upserts stable evidence IDs with `$setOnInsert`, preserving decisions and preventing duplication.

## 17. MongoDB Schema/Indexes

Collections and indexes:

- `student_accounts`: unique `student_id`, unique normalized `email`.
- `student_profiles`: unique `student_id`; internal resume sequence.
- `resumes`: unique `resume_id`, unique owner/hash, unique owner/version, owner/active.
- `resume_processing_runs`: unique processing ID and resume ID.
- `skill_evidence`: unique evidence ID, owner/skill, owner/resume.
- `gap_analysis_runs`: unique run ID, owner/created-at.

Standalone Mongo account/profile creation compensates the first insert if profile insertion fails.

## 18. Gap Analysis Rules

`gap-rules-v1` is explicit:

| Direct evidence for required canonical skill | Classification | Reason |
| --- | --- | --- |
| One or more confirmed, non-rejected records | `SUPPORTED` | `CONFIRMED_DIRECT_EVIDENCE` |
| One or more extracted, non-rejected records | `PARTIALLY_SUPPORTED` | `UNCONFIRMED_DIRECT_EVIDENCE` |
| None | `UNVERIFIED` | `NO_DIRECT_EVIDENCE` |

Rejected evidence is excluded. No graph-neighbor inference or numeric weighting occurs. Neo4j owns and supplies `CORE|EXPECTED|OPTIONAL` importance.

## 19. Gap Analysis Versioning

Every run is immutable and stores target role, profile version, SHA-256 of the evidence ID/skill/status/update snapshot, `careerpilot-knowledge-v1`, `gap-rules-v1`, timestamp, requirement assertion IDs, and evidence IDs used. This identifies whether profile/evidence, knowledge, or rules changed.

## 20. APIs

Added registration/token, profile get/update, resume upload/list/retry/delete, per-resume/all evidence read, evidence decision, gap create/read, and canonical skill-list endpoints. All live under `/api/v1`; private student endpoints require bearer identity. OpenAPI and centralized safe errors cover 401, 404, 409, 413, 415, 422, 500, and 503 cases.

## 21. Frontend Workflow

`StudentWorkspace` provides account creation/sign-in, private upload, version display, evidence provenance and decisions, canonical correction choices loaded from the API, canonical target-role selection, gap execution, and evidence-sensitive wording. It uses real typed client functions and contains no hardcoded role/skill results.

## 22. Privacy/Security

Files have generated keys and private storage. APIs do not return paths. Logs record operation, counts, duration, IDs/categories through request context; they do not record JWTs, passwords, bytes, resume text, or evidence text. Responses use `no-store` and `nosniff`. CORS is explicit. Owner filters prevent ID enumeration from becoming data access.

## 23. Failure Handling

If persistence fails after file save, the service removes the file. If extraction fails, metadata/file/processing history remain with `TEXT_EXTRACTION_FAILED`. If Neo4j fails during normalization, they remain `NORMALIZATION_FAILED`; a retry rereads the same private file. MongoDB failure returns 503. Neo4j failure does not erase MongoDB records or invent canonical skills. Deletion tombstones metadata and removes file, processing record, and derived evidence; historical gap snapshots remain.

## 24. Tests

Final verified counts:

| Suite | PASSED | FAILED | SKIPPED | NOT VERIFIED |
| --- | ---: | ---: | ---: | ---: |
| Backend non-integration | 76 | 0 | 0 | 0 |
| Backend real integration | 12 | 0 | 0 | 0 |
| Frontend full opt-in suite | 31 | 0 | 0 | 0 |

The final gate ran formatter, linter, strict typing, both backend test selections, every frontend test with opt-in integration enabled, and the production build. `deselected` tests in split backend commands are not reported as skipped; each complementary suite was run explicitly. Synthetic documents contain no personal data.

## 25. MongoDB Integration Verification

PASSED against MongoDB 8.0 on isolated port 27617: account/profile persistence, resume metadata and versions, processing transitions, evidence persistence and decisions, owner-scoped reads/writes, gap snapshots, unique indexes, repeated processing, deletion, and recovery. MongoDB-down private authentication returned 503; recovery returned healthy.

## 26. Neo4j Integration Verification

PASSED against Neo4j 5.26 Community on isolated port 7767 using the actual seeded dataset. Tests resolved actual Python, SQL, REST API, PostgreSQL aliases, canonical corrections, Backend Developer requirements, importance, assertions, and dataset version.

## 27. Cross-Database Verification

PASSED: MongoDB evidence plus Neo4j role requirements produced `SUPPORTED`, `PARTIALLY_SUPPORTED`, and `UNVERIFIED` in one deterministic run. No cross-store write transaction or graph mutation was introduced.

## 28. End-to-End Verification

PASSED through the production TypeScript frontend client and live Vite proxy: register -> actual synthetic PDF multipart upload -> FastAPI -> private Docker storage -> pypdf -> Neo4j normalization -> MongoDB evidence -> confirm Python -> canonical target role -> Neo4j requirements -> MongoDB gap snapshot -> decoded structured results. Assertions observed Python `SUPPORTED`, SQL `PARTIALLY_SUPPORTED`, at least one `UNVERIFIED`, and `careerpilot-knowledge-v1`.

The React component's auth/evidence-review/confirmation/role/gap rendered state transitions passed with controlled API responses. A manual interactive browser gesture walkthrough is **NOT VERIFIED** because no browser surface was available to the automation runtime; this is not represented as a live React integration pass.

## 29. Malicious Upload Testing

PASSED: traversal filename, `.exe`, fake PDF, wrong MIME, zero bytes, size boundary, malformed PDF, corrupt DOCX, unsafe archive characteristics, and no-text extraction. Real upload responses contained no traceback or storage path.

## 30. Authorization Testing

PASSED: missing JWT is 401; tampered JWT is rejected; Student A cannot read Student B resume evidence, modify Student B evidence, or retrieve Student B gap analysis. All three foreign-resource cases are owner-filtered server-side.

## 31. Performance Baselines

Local seven-run HTTP baseline against the isolated Docker dependencies (not production):

| Operation | Median | p95 |
| --- | ---: | ---: |
| PDF upload + extraction + normalization + persistence | 21.14 ms | 44.14 ms |
| Evidence retrieval | 3.97 ms | 5.47 ms |
| Role requirement retrieval | 6.38 ms | 26.81 ms |
| Gap analysis + snapshot persistence | 10.15 ms | 36.88 ms |

The likely production bottleneck is synchronous document parsing, followed by graph network latency. Run `python scripts/benchmark-phase3.py --iterations 7` against disposable infrastructure to reproduce.

## 32. Scaling Assessment

- **10 students:** current single process, local storage, and synchronous parsing are adequate.
- **1,000 students:** indexed MongoDB queries remain reasonable; use durable object storage, backups, rate limits, and bounded worker concurrency.
- **100,000 students:** move `StudentService.process` behind a durable job queue, horizontally scale stateless API/workers, use object storage and lifecycle policy, cache stable canonical lookups, capacity-plan Neo4j, shard/partition MongoDB only from measured load, and add token revocation/audit controls. A future LLM extractor would require a separate privacy-reviewed provider boundary and queue.

## 33. Regression Verification

PASSED: liveness/readiness, request IDs, safe errors, MongoDB and Neo4j connectivity, Phase 2 knowledge endpoints, graph ingestion/invariants/provenance, knowledge React component, CORS, frontend health client, and production build. The final backend set totals 88 passing tests across explicit unit and integration runs; the final frontend opt-in run has 31 passes, zero failures, and zero skips.

## 34. Security Review

Diff review found no trusted request `student_id`, public upload route, user filename storage path, resume/evidence content log, hardcoded frontend taxonomy/result, student graph write, `HAS_SKILL`, arbitrary score, LLM gap decision, or unbounded private list. Password/JWT/file settings are secret or bounded. Residual deployment controls are listed under limitations.

## 35. Files Added/Modified

Major additions are the student domain (`models`, `repository`, `auth`, `storage`, `extraction`, `service`, `routes`), MongoDB student adapter, student unit/real integration tests, React workspace and typed client/tests, actual dataset/knowledge code retained from Phase 2, private-volume Docker configuration, benchmark script, architecture/ADR documents, API contract, README, dependency locks, and this report. `git status` still contains the user's pre-existing uncommitted Phase 2 implementation; no commit, reset, push, or deployment was performed.

## 36. Known Limitations

- OCR/scanned PDFs, encrypted PDFs, legacy DOC, and image resumes are unsupported.
- Alias/section rules are intentionally small and English-oriented; unresolved is expected.
- Processing is synchronous and local storage is single-host.
- Tokens have no refresh/revocation flow; the React token is intentionally not persisted.
- Full account deletion, email verification/recovery, malware scanning, object storage, quotas/rate limiting, production TLS/secrets/database roles, backup/restore, and audit export are deployment/future work.
- Resume deletion retains gap snapshot references/hashes but removes their evidence text.
- Manual browser gesture verification is not verified in this environment.

## 37. Technical Debt

Introduce an async worker only after measured parsing load, add an object-storage adapter before multi-host deployment, add refresh/revocation and account lifecycle endpoints when product requirements exist, version the alias registry as its own reviewed artifact if it grows, and add browser E2E tooling when an approved browser runtime is available. None requires a Phase 4 vector stack.

## 38. Phase 3 Exit Checklist

All automated student, resume, skill, evidence, gap, security, database, quality, regression, outage/recovery, and documentation criteria are **PASSED**. Actual PDF and DOCX parsers and real databases were used. The manual interactive browser walkthrough is **NOT VERIFIED**; therefore the literal claim that every possible exit check passed is **No**. No required automated test was skipped.

## 39. Phase 4 Readiness

The backend evidence boundary is safe for Phase 4 experimentation: canonical IDs, provenance, owner isolation, evidence decisions, and reproducible gap inputs exist. Phase 4 may begin without changing these ownership rules. Production rollout and UI release signoff should first address the deployment controls and manual browser verification above. Phase 4 must keep extracted, confirmed, inferred, and retrieved evidence distinct.

## 40. Reproduction Commands

```powershell
./scripts/setup-env.ps1
docker compose -p careerpilot-integration -f compose.yaml -f compose.test.yaml up -d --wait --wait-timeout 240
$env:CP_RUN_INTEGRATION = '1'
$env:TEST_NEO4J_PASSWORD = (Select-String .env '^NEO4J_LOCAL_PASSWORD=').Line.Split('=',2)[1]
cd backend
.\.venv\Scripts\python.exe -m pytest -q -m "not integration"
.\.venv\Scripts\python.exe -m pytest -q -m integration
cd ..\frontend
npm.cmd run check
$env:CP_RUN_FRONTEND_INTEGRATION = '1'
npm.cmd test
cd ..
.\backend\.venv\Scripts\python.exe scripts\benchmark-phase3.py --iterations 7
docker compose -p careerpilot-integration -f compose.yaml -f compose.test.yaml --profile app down --volumes
```

For the live frontend integration, run the isolated backend on port 8001 and Vite with `BACKEND_PROXY_TARGET=http://127.0.0.1:8001` before setting `CP_RUN_FRONTEND_INTEGRATION=1`. See the root README for complete startup and outage commands.
