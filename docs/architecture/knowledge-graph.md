# Career knowledge graph

## Purpose and ownership

Neo4j is the canonical owner of reusable career knowledge. MongoDB remains the owner for future student and application state. The path is React → FastAPI knowledge routes → `KnowledgeService` → `KnowledgeRepository` protocol → Neo4j adapter. Domain models and validation contain no Cypher; all graph reads, schema operations, and writes are in `app/infrastructure/knowledge.py`.

```text
Company --OFFERS_ROLE--> CompanyRole --BASED_ON--> Role
                              |                     |
                              +--REQUIRES_SKILL----+--> Skill
Resource --TEACHES_SKILL------------------------------> Skill
Resource --COVERS_TOPIC--> InterviewTopic --ASSESSES_SKILL--> Skill
```

## Nodes

All canonical entities have `id`, `kind`, `name`, a validated JSON `payload`, `dataset_id`, and `dataset_version`. The JSON is parsed back into strict Pydantic types on reads. Skill also supports exact normalized aliases and category. Resource requires an HTTPS URL and stable content reference. Company and CompanyRole may be explicitly synthetic.

The six labels are `Skill`, `Role`, `Company`, `CompanyRole`, `Resource`, and `InterviewTopic`, always paired with `KnowledgeEntity`. `KnowledgeSource` stores source metadata/payload. `KnowledgeDataset` stores owner, version, validation time, and canonical content hash.

## Relationships

`OFFERS_ROLE` is Company → CompanyRole. `BASED_ON` is CompanyRole → Role. `REQUIRES_SKILL` is Role or CompanyRole → Skill. `TEACHES_SKILL` is Resource → Skill. `COVERS_TOPIC` is Resource → InterviewTopic. `ASSESSES_SKILL` is InterviewTopic → Skill. Validation rejects every other endpoint/direction.

Each relationship has a stable triple-derived ID, typed payload, dataset owner/version, and source IDs. `REQUIRES_SKILL` has `CORE`, `EXPECTED`, `OPTIONAL`, or explicit `UNSPECIFIED` importance. The graph has no numeric confidence score.

## Provenance

The implementation uses source nodes plus evidence embedded in each assertion payload. This keeps normal traversals direct while returning source title, URI, publisher, collection/publication timestamps, content hash, dataset version, evidence statement, locator, curation method, and validation time. Full assertion reification was rejected because every traversal would require extra nodes; relationship-only properties were rejected because shared source metadata would be duplicated.

Official documentation facts use `source_derived`; project-authored learning profiles use `manual_curated`; fictional company facts use `synthetic`. Every locator and evidence statement must exist verbatim in its hashed local observation note. Notes are original scope summaries, not copies of external pages.

## Identity and aliases

IDs are lowercase semantic identifiers with kind prefixes, such as `role_backend_developer`. Relationships hash the logical source/type/target triple. Names never determine identity. Skill aliases use Unicode NFKC, case folding, and whitespace collapse for exact lookup/collision detection; there is no fuzzy merging. IDs and entity kinds are immutable at ingestion.

## Constraints and access patterns

Fifteen uniqueness constraints cover IDs for six canonical labels, `KnowledgeEntity`, `KnowledgeSource`, `KnowledgeDataset`, and all six relationship types. Neo4j's backing range indexes support ID entry points and relationship provenance. Role listing intentionally scans the small Role label for substring search and deterministic sort. Traversals are one hop and pagination is bounded. PROFILE showed index entry for role/skill traversal and a relationship unique-index seek for provenance; there were no Cartesian products.

## Ingestion lifecycle

1. Parse a bounded JSON file and validate strict types, IDs, aliases, sources, endpoints, directions, duplicates, provenance, timestamps, importance, and company-role cardinality.
2. Resolve observation-note paths beneath the dataset directory and verify SHA-256 plus locator/evidence presence.
3. Open Neo4j, create idempotent constraints, and execute the entire snapshot write in one managed transaction.
4. Reject foreign ownership, kind changes, same-version hash changes, and downgrades; merge the snapshot and prune only records owned by `careerpilot_core`.
5. Inspect stored payloads, labels, directions, properties, content hash, provenance presence, and disconnected nodes by reconstructing and validating the dataset.

If validation fails, no connection is opened. If a graph write fails, the transaction rolls back. The CLI is the only write surface and requires `--accept-curated` for ingestion.

## Query examples and limits

The repository exposes entity list/detail, typed related entities with evidence, assertion provenance, and company context. HTTP routes validate stable-ID syntax and cap pagination. Missing data returns 404, dependency failure 503, inconsistent persisted data a sanitized 500, and request validation 422.

The seed is deliberately narrow. Learning-profile importance is project curation, not labor-market research. Resource coverage is introductory. The company is fictional. Phase 3 can extend sources and candidate-review tooling, but canonical publication must continue through this validation boundary.
