# Mock interview

Phase 6 supports text-only `TECHNICAL_CONCEPTUAL` and `ROLE_SPECIFIC` sessions. Groq selects distinct canonical `InterviewTopic` records from validated role/retrieval context; CareerPilot renders reviewed conceptual templates and attaches canonical skills/evidence deterministically. This prevents a valid topic from drifting into an unsupported sub-question. No coding sandbox, voice, video, emotion, or proprietary employer process is represented.

The lifecycle is `ACTIVE → response persisted → evaluation completed/retryable → COMPLETED`. A response is immutable. Provider failure cannot remove it and an identical retry can resume evaluation.

Every question receives a fixed rubric before the answer exists:

- `TECHNICAL_ACCURACY`
- `ROLE_RELEVANCE`
- `CLARITY`
- `GROUNDING`

Ratings are categorical: `STRONG`, `ADEQUATE`, `DEVELOPING`, `INSUFFICIENT`. They are not confidence or proficiency scores. Student answers and retrieved passages are delimited as untrusted data. Canonical skill/evidence IDs are attached deterministically after strict provider-schema validation.

An evaluation creates practice SkillEvidence only when technical accuracy and role relevance are not `INSUFFICIENT`. That evidence remains `EXTRACTED`; it can move a new gap run from `UNVERIFIED` to `PARTIALLY_SUPPORTED`, never directly to `SUPPORTED`. Session, question and evaluation IDs preserve provenance.
