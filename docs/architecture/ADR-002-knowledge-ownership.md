# ADR-002: Canonical knowledge ownership

Status: accepted, 2026-10-01.

Neo4j owns reusable career entities and relationships. MongoDB retains future student profiles, resume evidence, application state, and user workflow state. The knowledge module accesses Neo4j through a repository protocol inside the modular monolith.

Graph traversal and relationship evidence fit Neo4j. Putting student observations in the same canonical graph would blur sourced career facts with personal, mutable evidence and complicate deletion and access control. Phase 2 therefore creates no student nodes or skill-evidence relationships.
