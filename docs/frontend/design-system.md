# CareerPilot frontend design system

## Visual principles

CareerPilot uses a dark, evidence-led workspace rather than a marketing dashboard. The interface prioritizes preparation context, provenance, and the next useful action. Surfaces are layered with borders and restrained elevation so graph facts, student evidence, retrieved resources, and generated recommendations remain distinguishable.

## Color tokens

The implementation lives in `frontend/src/app/styles.css`.

| Token | Meaning |
| --- | --- |
| `--cp-bg` | Application background |
| `--cp-surface` | Primary panel surface |
| `--cp-raised` | Raised card and status surface |
| `--cp-interactive` | Button/control surface |
| `--cp-border`, `--cp-border-soft` | Strong and subtle dividers |
| `--cp-text`, `--cp-text-secondary`, `--cp-text-muted` | Text hierarchy |
| `--cp-brand`, `--cp-brand-strong` | CareerPilot identity and success |
| `--cp-info`, `--cp-warning`, `--cp-danger` | Informational, caution, and error states |
| `--cp-graph` | Canonical graph evidence |
| `--cp-student` | Student evidence |
| `--cp-retrieved` | Retrieved learning evidence |
| `--cp-generated` | Generated recommendation |

Color is paired with labels such as `graph fact`, `student status`, `retrieval evidence`, or `generated synthesis`; it is not the only semantic signal.

## Typography and spacing

Avenir Next or Segoe UI is used for interface text, with Georgia reserved for the main display statement. Labels use uppercase tracking sparingly. Existing spacing follows a compact 4/8/12/16/20/24/28/38/48 rhythm, with 14px cards and 7px controls.

## Components and patterns

- `App` owns the shell, system status, hash navigation, and global product framing.
- `KnowledgeExplorer` owns canonical graph exploration and provenance display.
- `StudentWorkspace` owns authenticated workflow state and API actions.
- Statuses use explicit text and `role="status"` or `role="alert"` where appropriate.
- Empty and unavailable states remain tied to real API responses; no domain metrics are fabricated.
- Hash sections provide direct links without adding a router dependency: `#overview`, `#evidence`, `#gap`, `#roadmap`, `#practice`, and `#readiness`.

## Motion and accessibility

Controls use short transform, border, and color transitions. The global `prefers-reduced-motion: reduce` rule disables smooth scrolling and reduces transitions/animations to near-zero duration. Keyboard focus uses a visible green outline. Native labels, selects, buttons, and textareas are retained for keyboard and screen-reader behavior.

Automated axe, screen-reader, and manual browser checks were not available during this phase and are recorded as NOT VERIFIED in `PHASE7_REPORT.md`.
