# Phase 1 architecture

```text
frontend/src/app/App.tsx
  -> frontend/src/api/health.ts (runtime contract validation)
  -> frontend/src/api/client.ts (URL, IDs, timeouts, cancellation, normalized failures)
  -> FastAPI API routers
  -> application/health.py (Dependency protocol + bounded concurrent health service)
  -> infrastructure/mongodb.py and infrastructure/neo4j.py
  -> MongoDB / Neo4j
```

`app/main.py` is the composition root. Settings load once; a FastAPI factory makes configuration and dependency injection explicit. Lifespan allocates each adapter once, probes it without requiring availability to start, then closes both adapters at shutdown. HTTP requests reuse connection pools. The outer request-context middleware assigns IDs and measures duration. CORS wraps the sanitized-error middleware so error responses receive allowed-origin headers too. Validation and framework errors use centralized handlers. Request IDs reset after each request using ContextVar tokens.

Liveness is independent of external databases. Readiness runs both dependency checks concurrently with a per-check deadline. It returns individual safe states, never raw driver errors. Neo4j verifies the driver and performs a read-only query in the configured database; MongoDB pings the configured database. Missing credentials or timeouts are failures, without fallback. Pool connectivity recovers after transient outages; changes to configuration require restart.

Logs include an allowlist of operational fields. Paths are recorded as route templates, without query strings, arbitrary unmatched paths, credentials, driver exception messages or request bodies. Production configuration must be explicit. CORS does not grant private-resource ownership; future authenticated APIs must enforce ownership independently.

## Data ownership and extension points

| Future capability | Intended boundary / ownership |
| --- | --- |
| Auth and profile | Domain/application modules; MongoDB authoritative; every private query scoped to authenticated owner |
| Resume processing | Application use cases invoke parsing/evidence adapters; metadata and student evidence in MongoDB |
| Knowledge ingestion | Knowledge module validates canonical entities and relationships before Neo4j writes; Phase 2 owns schema |
| FAISS retrieval | Retrieval application interface; rebuildable derived semantic index, never authoritative student/graph state |
| Hybrid retrieval / evidence fusion | Retrieval interfaces compose graph/vector adapters and preserve source identifiers |
| Orchestrator | Application layer coordinates module interfaces; run/evidence metadata in MongoDB |
| LLM gateway | Provider-independent application interface with infrastructure implementations when needed |
| Roadmap, company preparation, interview, readiness | Domain use cases added with real requirements; student sessions/results in MongoDB |

No schema, parser, authentication, graph seed, embedding, agent framework or LLM provider is implemented in Phase 1. Later domain modules must not import `pymongo` or `neo4j`; application services accept purpose-specific interfaces. Avoid creating speculative repository interfaces now.

## Operational limits

Health is a bounded point-in-time probe, not proof of all future database operations or user permissions. The local Compose MongoDB instance is unauthenticated and loopback-bound. Health endpoints and API documentation are public in this phase. Rate limiting, production database roles, TLS, authentication and ownership enforcement belong to later security/deployment work before private student data is accepted. Shutdown reports sanitized close failures and attempts all resources; a permanently hung external driver can only receive a bounded cleanup attempt.
