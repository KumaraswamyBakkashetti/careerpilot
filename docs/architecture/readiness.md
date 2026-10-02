# Explainable readiness

`readiness-rules-v1` is deterministic and versioned. It measures preparation evidence, not employability or hiring probability.

| Component | Rule | Weight |
| --- | --- | ---: |
| Role skill coverage | importance-weighted gap state: supported 100, partial 50, unverified 0; CORE=3, EXPECTED=2, other=1 | 50% |
| Evidence completeness | percentage of required skills with non-rejected resume or practice evidence | 25% |
| Interview practice | percentage of required skills covered by a completed structured evaluation | 25% |

The weighted value is rounded to an integer. Categories are `FOUNDATION` (0–24), `DEVELOPING` (25–49), `PREPARING` (50–74), and `WELL_PREPARED` (75–100). Each immutable snapshot retains component values, evidence IDs, priority skill IDs, source gap run, rule version, version number, and the non-probability limitation.

Contradictory/rejected evidence is ignored. Practice may improve completeness and interview-practice components while remaining unconfirmed in role coverage until a later gap run applies the explicit partial-support rule.
