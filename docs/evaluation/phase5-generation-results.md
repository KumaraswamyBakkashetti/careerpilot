# Phase 5 Generation Evaluation

Executed: 2026-10-01T19:15:42.835583+00:00  
Dataset: `careerpilot-generation-eval-v1` (4 cases)  
Model: `openai/gpt-oss-120b`; reasoning `medium`  
Mode: `strict_json_schema`

| Metric | Result |
|---|---:|
| Schema validity | 100.0% |
| Grounding validity | 100.0% |
| Unsupported-claim rate | 0.0% |
| Evidence-reference validity | 100.0% |
| Requirement coverage | 100.0% |
| Constraint adherence | 100.0% |
| Provider failure rate | 0.0% |

Latency median/p95: 1396.861/1666.980 ms.  
Token totals: `{"completion_tokens": 1825, "prompt_tokens": 2409, "reasoning_tokens": 1356, "total_tokens": 4234}`.

The injection fixture embeds an instruction to recommend Kubernetes and an unknown resource ID
inside resource data. Results are accepted only after deterministic grounding and reference
validation.

Controlled prototype evaluation over four small synthetic EvidenceBundles; not general model performance.
