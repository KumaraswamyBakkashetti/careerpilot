# CareerPilot Phase 5 Implementation Report

Verification date: 2026-10-02 (Asia/Calcutta)  
Scope: grounded personalized learning-roadmap generation; no Phase 6 agents

## 1. Executive Summary

Phase 5 implements a provider-independent LLM gateway, live Groq discovery, strict structured roadmap generation, deterministic grounding/reference validation, owner-scoped persistence, explicit partial coverage, a React roadmap experience, and controlled evaluation. The LLM synthesizes supplied evidence; it does not create canonical facts or student evidence.

## 2. Phase 4 Baseline

Verified: 4 resources, 21 chunks, deterministic 420/40 chunking, `all-MiniLM-L6-v2` at revision `1110a243...`, 384 dimensions, normalized FAISS `IndexFlatIP`, and deterministic graph/vector/hybrid retrieval. Baseline gates passed: 83 backend unit tests and 28 frontend tests; 12 backend and 3 frontend opt-in tests were initially deselected/skipped. Phase 4 results remain small controlled prototype results, not general retrieval performance.

## 3. Architecture

`GapAnalysisRun -> EvidenceBundle(s) -> deterministic envelope -> roadmap-prompt-v1 -> LLMGateway -> GroqAdapter -> strict JSON Schema -> Pydantic -> grounding/reference validation -> MongoDB -> React`. See `docs/architecture/llm-generation.md`.

## 4. Groq Provider Decision

Groq is the initial provider. Domain/application code depends on `LLMGateway`, not provider HTTP types or a Groq SDK. This preserves replacement and testing boundaries.

## 5. Live Model Discovery

The authenticated Groq Models API was queried on 2026-10-02. The sanitized CLI independently repeated discovery and strict-schema smoke verification. No API key was logged or reported. Machine-readable sanitized evidence is in `docs/evaluation/phase5-model-discovery.json`.

## 6. Models Available During Verification

Eleven project-visible active models were returned: `allam-2-7b`, two Canopy Labs Orpheus models, two Llama Prompt Guard models, `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `openai/gpt-oss-safeguard-20b`, `qwen/qwen3.8-27b`, and two Whisper models. GPT-OSS 120B and 20B reported 131,072-token context windows.

## 7. Preferred Model Verification

`openai/gpt-oss-120b` was present, active, documented by Groq as a production model, and passed a real `strict=true` JSON Schema request. CLI smoke: 639.747 ms, 178 prompt tokens, 77 completion tokens, 56 reasoning tokens, 255 total.

## 8. Selected Model

Selected: `openai/gpt-oss-120b`, configuration-driven through `Settings.groq_model` / `CP_GROQ_MODEL`.

## 9. Model Selection Failure or Change

No model change occurred. An initial PowerShell smoke diagnostic failed locally while inspecting headers; correcting the client script produced a pass. A pre-final multi-item contract that made the model echo deterministic priorities and reference arrays produced two classified strict-output 400s across repeated E2E attempts. They were not retried and no model was switched. The design issue was removed: the final provider schema contains only fields the model owns (`skill_id`, recommendation, activities), while CareerPilot attaches all deterministic fields and references. The final contract passed the regenerated evaluation plus consecutive cold/warm E2E runs.

## 10. LLMGateway

The protocol exposes `generate_structured`, `health_check`, `model_info`, and `close`, with typed requests, results, health, usage, and provider error categories.

## 11. GroqAdapter

The adapter owns HTTPS auth, model/reasoning configuration, strict-schema request construction, timeout, bounded network/5xx retry, non-retry classification, safe response extraction, usage, and latency. It contains no roadmap rules.

## 12. Structured Output

Chat Completions uses non-streaming JSON Schema with `strict=true`, all properties required, and `additionalProperties=false`. Pydantic validates again. No prompt-only JSON contract is trusted.

## 13. Prompt Architecture

The system message defines immutable grounding rules. The user message contains delimited structured data. Retrieved text is explicitly untrusted data. The model may write recommendation prose and activities only.

## 14. Prompt Version

`roadmap-prompt-v1`; persisted with model, evidence-bundle version, traces, timestamps, and usage.

## 15. Privacy Minimization

The projection excludes student ID/name, contact details, filename, raw resume, JWT, password, and storage path. Logs exclude prompt bodies, generated private content, secrets, and chain-of-thought.

## 16. EvidenceBundle Input

Inputs contain target role ID, finite student status/importance, graph assertions, selected resource chunks, provenance, and allowlisted IDs. Student identity present in Phase 4 bundles is deliberately dropped by the prompt builder.

## 17. Roadmap Schema

Roadmaps store owner, target/gap IDs, immutable version, provider/model/prompt/evidence versions, trace IDs, coverage status, omitted skills, validated items, and typed evidence. The provider returns only skill ID, recommendation, and activities. CareerPilot then attaches deterministic priority/reason/sequence and all resource/evidence IDs before validation and persistence.

## 18. Grounding Validator

It requires exact skill coverage for the supplied envelope and rejects changed priority, reason code, sequence, unknown skills, and explicit unsupported deficiency wording such as “you lack”/“you are bad.”

## 19. Evidence Reference Validator

It rejects unknown evidence/resource IDs and requires each item to cite the role assertion, student-status fact, and at least one retrieved chunk/resource.

## 20. Priority and Ordering Rules

CORE+UNVERIFIED is HIGH; remaining CORE and EXPECTED+UNVERIFIED are MEDIUM; other actionable gaps are LOW. Ordering is deterministic by priority, importance, then skill ID. The model cannot change it.

## 21. Generation Runs

Runs store task, owner, model, prompt, gap, input IDs, traces, status/category, total/retrieval/provider/validation/persistence latency, token counts, timestamps, request identity, and roadmap output ID. Hidden reasoning content is not stored.

## 22. Persistence

Only fully validated Roadmaps enter MongoDB. Failed runs remain diagnostic metadata without a canonical roadmap.

## 23. Versioning and Idempotency

The SHA-256 request identity includes student, gap snapshot, prompt/model, retrieval versions, and idempotency key. Equivalent create requests reuse completed output. Regeneration requires a key and preserves history.

## 24. APIs

Implemented authenticated task routes: create/list/get/evidence/regenerate plus sanitized model health. No raw `/llm` or `/groq` endpoint exists.

## 25. Frontend

React provides **Generate grounded learning roadmap** after gap analysis and renders requirement facts, student evidence status, resource evidence, and generated synthesis separately. Partial coverage names omitted skills. Hidden reasoning is absent.

## 26. Model Health

Authenticated diagnostics report provider, configured model, key configuration state, live availability, strict-output mode, status, and safe category. It does not affect core readiness.

## 27. Rate Limits

429 maps to `RATE_LIMITED`, captures `Retry-After` when present, and is not retried. Controlled adapter simulation passed. Live rate-limit exhaustion was intentionally not attempted; live rate-limit-header verification is NOT VERIFIED.

## 28. Retry Policy

Default one bounded exponential retry applies only to network/timeout and selected 5xx failures. Authentication, permission, model, 400/schema, and 429 failures are not blindly retried.

## 29. Failure Handling

Distinct categories exist for model unavailable/forbidden, provider unavailable, rate limited, invalid provider/structured configuration, malformed/schema output, grounding, evidence reference, and insufficient evidence. UI messages are safe.

## 30. Provider Outage

Adapter timeout/network behavior is simulated and deterministic features are architecturally/provider-state independent. A real forced Groq outage was NOT VERIFIED; existing deterministic endpoints remained live during the isolated structured-output request failure.

## 31. Prompt Injection Tests

Unit and live evaluation used resource text instructing the model to ignore instructions and recommend Kubernetes/fake resources. The live result passed grounding/reference validation and contained neither prohibited output.

## 32. Hallucination Tests

Unknown skill/resource IDs and unsupported ability claims are rejected before persistence. Unit tests verify all three paths.

## 33. Evaluation Dataset

`careerpilot-generation-eval-v1` contains 4 controlled EvidenceBundles covering Python, SQL, HTML, pytest, CORE/EXPECTED, UNVERIFIED/PARTIALLY_SUPPORTED, prohibited claims, and injection. It is intentionally small.

## 34. Schema Validity

4/4, 100%.

## 35. Grounding Validity

4/4, 100%.

## 36. Unsupported-Claim Rate

0/4, 0%.

## 37. Evidence-Reference Validity

4/4, 100%.

## 38. Requirement Coverage and Constraint Adherence

Both were 4/4, 100% over the supplied single-skill cases.

## 39. Latency

Evaluation LLM median/p95: 1,396.862/1,666.980 ms. Final warm real full flow: 2,151.495 ms total, 231.546 ms retrieval, 1,900.743 ms Groq, 0.089 ms validation, and 2.553 ms persistence. Final cold full flow: 10,698.804 ms total, 8,632.954 ms retrieval/model initialization, and 2,050.117 ms Groq. Groq dominates warm latency; local model initialization dominates cold latency.

## 40. Token Usage

Four primary cases: 2,409 prompt, 1,825 completion, 1,356 reasoning, 4,234 total tokens. Final warm E2E: 1,989 prompt, 584 completion, 319 reasoning, 2,573 total.

## 41. Model Comparison

One matched case: 120B/medium passed at 1,666.980 ms (1,075 total tokens); 20B/medium passed at 967.624 ms (825 total). One case is insufficient to change the selected production configuration.

## 42. Reasoning-Effort Experiment

On the same case, 120B/low passed at 923.823 ms with 788 total tokens versus medium at 1,666.980 ms with 1,075. The sample is too small to conclude equivalent roadmap quality; medium remains selected.

## 43. Privacy Payload Verification

The actual adapter request object was captured at the HTTP boundary in a safe contract test. It contained only the minimized skill payload, strict schema, system instructions, and safe generation settings; prohibited private fields and tools were absent. Live request content was not logged.

## 44. Security Review

Key is `SecretStr`, server-only, unlogged, and excluded from React. Ownership filters roadmap/run reads. IDs, priorities, statuses, and references are allowlisted. Resource injection is data-delimited. There is no web/code tool, raw inference route, arbitrary model fallback, prompt logging, or chain-of-thought storage.

## 45. Regression

Phase 1-4 unit behavior remained green. Final integration and build counts are recorded below after the complete gate.

## 46. Backend Tests

Final unit gate: 99 passes with 12 opt-in integration tests deselected. Separate real MongoDB/Neo4j integration gate: 12 passes, 99 deselected.

## 47. Frontend Tests

29 ordinary tests pass; 3 opt-in tests are normally skipped. The explicit live run passed all 3, including the authenticated full roadmap flow.

## 48. Real Groq Integration

PASS: discovery, strict smoke, four-case evaluation, two controlled experiments, and successful cold/warm full flows used the live account and selected model.

## 49. Real End-to-End

PASS through the real frontend API client/Vite/FastAPI/MongoDB/Neo4j/FAISS/Groq/persistence path. React rendering is covered with component tests; a manual interactive browser gesture walkthrough is NOT VERIFIED.

## 50. Quality Gates

PASS: Ruff format/check, strict mypy over 56 source files, 99 backend unit tests, 12 real backend integration tests, frontend Prettier/ESLint/TypeScript, 29 ordinary frontend tests, 3 explicit live frontend integration tests, production frontend build, Compose validation, and backend Docker build.

## 51. Known Limitations

Four resources and four evaluation cases are too small for general claims. Some role gaps have no resource, so roadmaps are explicitly partial. Cold local embedding load is slow. The superseded echo-heavy provider contract produced repeatable 400s; the reduced final contract passed all reruns, but broader production sampling is still needed. No calibrated load test, manual browser walkthrough, or forced real Groq outage was performed.

## 52. Technical Debt

Broaden reviewed resources/evaluation, preload the embedding model, add operational concurrency admission after measurement, expose safe run diagnostics to administrators, test real rate headers when naturally observed, and add browser automation. Do not add queues or fallback routing without evidence.

## 53. Phase 5 Exit Checklist

Core discovery, selected-model smoke, gateway/adapter, privacy, strict schema, application/grounding/reference validation, roadmap persistence/versioning/ownership, failure simulation, evaluation, real databases/FAISS/Groq, frontend client E2E, and automated gates pass. Real forced provider outage, natural live 429 metadata, and manual browser interaction are NOT VERIFIED. Therefore the literal answer that every Phase 5 exit item passed is **No**.

## 54. Phase 6 Readiness

The technical boundary is suitable for scoped Phase 6 planning, but Phase 6 should not begin as an unconditional release gate until the NOT VERIFIED operational checks and broader corpus/evaluation are addressed. No Phase 6 agent was implemented.

## 55. Reproduction Commands

```bat
cd /d C:\Users\kumar\Downloads\CareerPilot\CareerPilot
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\check.ps1
cd backend
.venv\Scripts\python.exe -m app.modules.llm.cli --smoke
.venv\Scripts\python.exe ..\scripts\evaluate-phase5.py --compare
cd ..
docker compose -p careerpilot-integration -f compose.yaml -f compose.test.yaml up -d --wait --wait-timeout 240
set CP_RUN_INTEGRATION=1
backend\.venv\Scripts\python.exe -m pytest -q -m integration backend\tests
npm.cmd run check --prefix frontend
docker compose config
docker compose build backend
```

Results: `docs/evaluation/phase5-generation-results.json`, `.md`, and `phase5-model-discovery.json`.
