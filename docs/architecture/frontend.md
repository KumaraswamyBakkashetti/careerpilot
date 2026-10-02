# Frontend architecture

## Runtime shape

CareerPilot is a React 19 + TypeScript + Vite application. `App` is the composition root for the product shell and system health check. The authenticated workflow remains in `StudentWorkspace`, which calls the existing typed API functions in `frontend/src/api/student.ts`. `StudentWorkspace` reports only the boolean session boundary to `App`; the bearer token remains private to the workflow component.

The frontend uses a central `ApiClient` for request IDs, bearer headers, cancellation, timeouts, JSON parsing, and normalized `ApiError` values. No raw feature-level `fetch` calls or second state-management library were introduced.

## Navigation

The product is a single application entry point with hash-addressable workflow surfaces:

- `#overview` and `#status`
- `#profile`
- `#evidence`
- `#gap`
- `#roadmap`
- `#interview`
- `#company-prep`
- `#readiness`

Private navigation and workflow sections render only after authentication. Before login, the shell exposes the auth screen and public system diagnostic without pretending profile, roadmap, interview, or company anchors are available. A full router can be added when separate route-level loading and access policies become necessary.

## Feature boundaries

`KnowledgeExplorer` displays canonical Neo4j-backed roles, skills, and provenance. `StudentWorkspace` coordinates private profile, resume, evidence, gap, retrieval, roadmap, company, interview, and readiness APIs. Backend contracts and domain rules remain protected.

## State and failure handling

Feature state is local React state and effects. The bearer token remains in memory by design. Loading, empty, dependency outage, provider-unavailable, and validation states are represented by existing components and safe API error mapping. No fake fallback metrics are inserted when a service is unavailable.

## Design system and motion

Global semantic tokens, surfaces, typography, evidence semantics, focus treatment, responsive breakpoints, and reduced-motion behavior live in `frontend/src/app/styles.css` and are documented in `docs/frontend/design-system.md`. CSS transitions are used instead of adding an animation dependency.

## Responsive strategy

The primary layout uses a 174px navigation rail beside a fluid content column on desktop. At 820px the rail becomes a horizontal scrollable navigation strip; at 560px controls and workflow grids stack. Content sections use `scroll-margin-top` so hash navigation remains legible below the top bar.

## Verification boundary

Frontend format, lint, TypeScript, unit tests, and production build are executable locally. Browser click-through, network inspection, console inspection, screenshot comparison, axe, and screen-reader verification are recorded separately when run.
