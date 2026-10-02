# Orchestration

`specialist-orchestrator-v1` records deterministic workflow selection for explicit actions. It is an observability and boundary layer, not a general tool-running endpoint.

An `OrchestrationRun` contains owner, task type, completed module/action steps, retrieval trace IDs, generation run IDs, result ID, status, duration and timestamp. It does not store chain of thought. Current finite task types are company preparation, interview and readiness; roadmap retains its Phase 5 generation trace.

MongoDB unique request identities guard company preparation, interview creation and readiness calculation. Answer uniqueness is defined by session and question, and a second different answer is rejected. All reads are owner-filtered.

Natural-language routing and arbitrary tool execution are intentionally absent. UI buttons and task-oriented API routes already convey intent without an LLM classifier.
