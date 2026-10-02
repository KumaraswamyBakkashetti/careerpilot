# CareerPilot mockup fidelity analysis

Verification date: 2026-10-02

## Reference inventory and naming

The supplied attachment does not expose original image filenames to the workspace. For traceability, this analysis uses descriptive names:

- `reference-dashboard.png`: the large first image showing the desktop dashboard with the PrepMate-style shell, mountain hero, KPI row, gap chart, learning path, assistant, recommendations, activity, interview practice, and progress cards.
- `reference-screen-collage.png`: the second image containing the smaller dashboard and profile row, then Resume & Evidence, Gap Analysis, Personalized Roadmap, Mock Interviews, Company Preparation, Learning Hub, and Analytics screens.

These names describe the supplied references only; they are not copied product assets and are not added to the repository.

## Global visual language

| Dimension | Observation from references | Fidelity implication |
| --- | --- | --- |
| Overall composition | Dense desktop application with a narrow dark rail, compact top bar, and a multi-column content canvas. | The current single-column long scroll must become a dashboard-like application frame with screen-level panels. |
| Sidebar width | Approximately 170-185px at a 1440px viewport, around 12-13% of the canvas. | Use a compact 174px rail, not the current 210px rail. |
| Sidebar structure | Brand lockup at top; grouped primary links with small white line icons; vivid indigo active row; settings/help anchored at bottom; profile is in top right. | Preserve a sticky rail with compact rows, icon slots, active left/filled treatment, and bottom utility group. |
| Topbar structure | 48-58px high, dark translucent surface, search field at left of content, notification bell and user avatar/menu at right. | Add a compact topbar separate from the rail; keep system status as a subtle utility rather than the dominant content. |
| Page padding | Roughly 16-20px from rail/content boundary, 20-24px panel gutters. | Use tight 16px outer content padding and 10-14px grid gaps. |
| Grid structure | Dashboard uses a 12-column feel: hero full width, four KPI cards, then a wide gap card plus learning path plus assistant/activity rail, followed by recommendation and practice sections. | Implement explicit dashboard grid areas instead of stacking every workflow section. |
| Number of columns | 4 KPI columns; lower regions use 2/3/1 and 8/4 splits. | Use CSS grid with stable minmax tracks and feature-specific spans. |
| Card proportions | Compact cards with 8-12px radii; hero is approximately 2.5:1; metric cards are short; charts are medium-height; lists are dense. | Avoid oversized white-space panels and use controlled min heights. |
| Typography hierarchy | Bold geometric sans headings; dashboard greeting around 30-36px; card headings 13-15px; metadata 9-11px; metrics 20-28px. | Use a modern sans stack with tight display scale and no serif hero. |
| Heading scale | Large greeting dominates only the hero. Screen titles are 20-24px. | Reduce the current 72px editorial heading for application screens. |
| Body scale | 11-13px dense UI copy, 9-10px metadata. | Use compact body and metadata tokens with sufficient contrast. |
| Metric scale | 20-28px, usually paired with a tiny label and status line. | Use real API-derived values only; preserve metric card geometry when data exists. |
| Color hierarchy | Deep navy/black background; elevated blue-black cards; white primary text; lavender/indigo primary accent; cyan, green, amber, and coral semantic accents. | Replace the current green-only palette with indigo/blue semantic tokens and retain evidence colors. |
| Background treatment | Near-black navy with subtle blue-violet ambient lighting; no flat white canvas. | Use layered navy surfaces and restrained radial lighting at the app level. |
| Surface treatment | Cards are blue-black with faint blue borders, subtle inner highlight, and selective glow on key active surfaces. | Define surface, elevated, interactive, and accent-card variants. |
| Gradients | Hero image has a dark overlay; active controls use blue-to-violet gradient; selected chart accents use cyan/green. | Use gradients only for active/hero accents, not every card. |
| Glow effects | Small violet/cyan glows around active buttons, chart rings, and hero lighting. | Use low-opacity box-shadow and radial accents sparingly. |
| Border treatment | 1px low-contrast blue-gray borders, occasionally violet on selected controls. | Use 1px `--cp-border-subtle`; reserve accent borders for active states. |
| Radius treatment | Mostly 8-12px, with 4-6px controls; no large pill-heavy design. | Reduce the current 14-18px card radii and keep controls compact. |
| Shadows | Soft dark elevation, not bright outlines. | Use layered black shadow with a restrained blue ambient component. |
| Icon treatment | Consistent compact line/filled icons in 28-36px colored squares or circles. | Use a single CSS icon slot system with accessible text; do not mix emoji/icon packs. |
| Chart treatment | Donut/ring with center value, thin bars, small labels, cyan/green/amber status colors. | Use CSS/SVG-free existing markup where possible; provide adjacent text values. |
| Progress treatment | Thin progress rails with vivid accent fill, percentage at end, and status labels. | Use real readiness/readiness component values and roadmap statuses. |
| Button treatment | Compact indigo gradient buttons, 10-12px labels, arrow or chevron affordance, border-only secondary buttons. | Add `button-primary`, `button-secondary`, and compact action variants. |
| Badge treatment | Small dark badges with colored text/border for Core, Expected, status, source type, and resource type. | Preserve domain terms and visual evidence semantics. |
| Whitespace | Dense but not cramped; dashboard fills the viewport with little unused vertical space. | Prefer stable rows and compact sections over long isolated panels. |
| Information density | High; multiple modules visible at once. | Add screen-level navigation and dashboard summaries without fabricating values. |
| Alignment | Strong left edges, consistent card gutters, aligned KPI baselines, and right-aligned action buttons. | Use shared grid and panel header primitives. |
| Visual anchors | Brand, active rail item, greeting/hero image, donut center value, vivid readiness ring, violet action buttons. | Keep these anchors real-data-driven and repeat them consistently across screens. |
| Implied interactions | Sidebar screen changes, search, profile menu, view-more buttons, expandable roadmap items, tabs, resource filters, and interview cards. | Implement only interactions supported by existing APIs; use anchors/tabs for existing state. |

## Reference: `reference-dashboard.png`

| Dimension | Analysis |
| --- | --- |
| Intended screen | `/overview` equivalent; current application anchor is `#overview`. |
| Composition | Persistent rail and topbar; hero banner; four KPI cards; lower three-column workspace; recommendation strip; interview practice strip; progress rail. |
| Hero | Full-width image-led banner, roughly 120px tall, with greeting at left and a translucent goal card at right. The image is a mountain scene with a dark navy overlay and warm sunset focal point. |
| KPI row | Four equal compact cards: target role, total skills, learning resources, interview readiness. Each has a colored icon square, label, main value, and small supporting line. |
| Main analytics row | Left: skill-gap donut with center total and three status rows. Middle: priority learning path list with numbered colored markers and compact action buttons. Right: AI assistant card above recent activity. |
| Lower content | Full-width latest recommendations card with four resource cards. Under it, interview practice cards and a compact progress summary. |
| Geometry | Content begins immediately below hero with 10-12px gaps; no giant page title. Cards align on a dense baseline. |
| Real-data adaptation | KPI slots map to current target role, gap item counts, retrieved/roadmap resource counts, and readiness only when API data exists. Empty states replace absent values. |

## Reference: `reference-screen-collage.png`

| Region | Intended route/anchor | Composition and implementation implication |
| --- | --- | --- |
| Dashboard thumbnail | `/overview` / `#overview` | Same dashboard geometry as the large reference; use as cross-check for density. |
| Profile thumbnail | `/profile` equivalent; current supported surface is authenticated workspace profile context | Two-column identity panel: avatar/profile summary at left, About Me/education/career/interests at center, profile completion rail at right. Only display name and target role are real today; unsupported fields must remain absent or clearly unavailable. |
| Resume & Evidence | `/resume` equivalent; current anchor `#evidence` | Screen title and tabs at top; upload button right; left resume/version list, center evidence table/list, compact status badges and action buttons. Use real resume history/evidence; retain unresolved and practice evidence semantics. |
| Gap Analysis | `/skills` equivalent; current anchor `#gap` | Header and tabs, three summary status cards, filters, then dense skill table with importance/status/evidence/action columns. Preserve `SUPPORTED`, `PARTIALLY_SUPPORTED`, `UNVERIFIED`, and `CORE/EXPECTED/OPTIONAL`. |
| Personalized Roadmap | `/roadmap` / `#roadmap` | Header with generate action, compact summary cards, tab strip, then vertical numbered timeline. Each item has priority badge, status, evidence/resource counts, and expandable detail. Use actual roadmap items and partial coverage. |
| Mock Interviews | `/interview` equivalent; current anchor `#practice` plus `#interview` | Header, interview type cards, popular session cards, practice stats ring. Setup and active session should be visually separated while using the existing APIs. |
| Company Preparation | `/company` equivalent; current anchor `#company-prep` | Header/search/filter surface and company cards in reference; current API only supports the synthetic company and company role. Retain explicit synthetic label and render real preparation facts/items. |
| Learning Hub | `/resources` equivalent; no dedicated current API route | Only expose resource content already returned by retrieval/roadmap APIs; do not add a dead route or invented catalog. |
| Analytics / Readiness | `/readiness` / `#readiness` | Header with tabs and compact KPI cards, progress-over-time area, skill-category progress bars. Current readiness API supports overall score, components, weights, explanations, and priority IDs; no historical chart should be fabricated. |

## Authentication visual mapping

No dedicated authentication reference was supplied. Login and registration should reuse the exact shell palette, typography, indigo/violet action treatment, navy layered background, subtle ambient lighting, compact controls, and evidence/trust language of the supplied screens. They should be a focused two-column auth composition rather than a generic white card.

## Fidelity checklist baseline

| Screen | Layout | Spacing | Typography | Color | Cards | Density | Alignment | Interactions | Responsive | Real-data mapping |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Overview | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT |
| Profile | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | PASS for supported fields |
| Resume & Evidence | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | PASS |
| Skill Gap | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | PASS |
| Roadmap | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | PASS |
| Company Preparation | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | PASS for existing API surface |
| Interview | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | PASS for existing API surface |
| Readiness | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | PASS |

The table is the pre-rework baseline. It is intentionally not a numerical fidelity claim.

## Post-rework checklist

| Screen | Layout | Spacing | Typography | Color | Cards | Density | Alignment | Interactions | Responsive | Real-data mapping |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Login / Registration | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Overview dashboard | PASS for controlled layout | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS at tested widths | PASS for available state |
| Profile | NEEDS REFINEMENT | NEEDS REFINEMENT | PASS shared system | PASS shared system | NEEDS REFINEMENT | NEEDS REFINEMENT | NEEDS REFINEMENT | PASS for existing controls | PASS shared shell | PASS for supported fields |
| Resume & Evidence | PASS shared card system | PASS shared card system | PASS | PASS | PASS | PASS | PASS | PASS | PASS at tested widths | PASS |
| Skill Gap | PASS shared card system | PASS shared card system | PASS | PASS | PASS | PASS | PASS | PASS | PASS at tested widths | PASS |
| Roadmap | PASS shared card system | PASS shared card system | PASS | PASS | PASS | PASS | PASS | PASS | PASS at tested widths | PASS |
| Company Preparation | PASS shared card system | PASS shared card system | PASS | PASS | PASS | PASS | PASS | PASS | PASS at tested widths | PASS for existing API surface |
| Interview | PASS shared card system | PASS shared card system | PASS | PASS | PASS | PASS | PASS | PASS | PASS at tested widths | PASS for existing API surface |
| Readiness / Analytics | PASS shared card system | PASS shared card system | PASS | PASS | PASS | PASS | PASS | PASS | PASS at tested widths | PASS |

PASS here means the implemented surface was checked against the supplied visual grammar and available browser evidence; it is not an image-diff score.
