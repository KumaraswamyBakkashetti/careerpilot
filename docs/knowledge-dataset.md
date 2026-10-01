# CareerPilot knowledge dataset v1

Version: `careerpilot-knowledge-v1`  
Owner: `careerpilot_core`  
Validated: 2026-10-01

| Kind | Count |
| --- | ---: |
| Skill | 20 |
| Role | 5 |
| InterviewTopic | 5 |
| Resource | 4 |
| Company | 1 |
| CompanyRole | 1 |

| Relationship | Count |
| --- | ---: |
| REQUIRES_SKILL | 42 |
| ASSESSES_SKILL | 10 |
| TEACHES_SKILL | 9 |
| COVERS_TOPIC | 4 |
| OFFERS_ROLE | 1 |
| BASED_ON | 1 |

Six sources are present: one project-authored curated learning-profile note, one explicitly synthetic company note, and four original observation notes referencing official Python, PostgreSQL, MDN, and pytest documentation. The five role profiles and their importance values are manual CareerPilot curation. They are learning profiles, not universal hiring requirements or employer claims. `CareerPilot Demo Labs` and its company role are fictional. Resource-to-skill/topic assertions are narrow source-derived scope mappings.

Validation checks strict fields, IDs and prefixes, unique/normalized names and aliases, known references, directions, duplicate triples, importance, timestamps, source methods, synthetic markers, company-role cardinality, note confinement, hashes, and evidence locators. Graph inspection repeats semantic validation and compares stored labels, endpoints, types, properties, provenance, hash, and connectivity.

Coverage is intentionally small: five generalized roles, introductory official resources, and five discussion topics. There is no hiring-market sampling, seniority model, geography, compensation, job-posting corpus, or real-company claim. Expanding coverage requires a new dataset version and the same review/validation boundary.
