# Phase 4 retrieval evaluation

Generated from `careerpilot-retrieval-eval-v1` with 12 manually labelled cases.

Graph-only is evaluated for structural role-requirement coverage elsewhere; it cannot return resource passages, so text-retrieval precision is not assigned to it.

| Model | Chunk / overlap | Chunks | k | Strategy | P@k | R@k | MRR | Median ms | p95 ms |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| sentence-transformers/all-MiniLM-L6-v2 | 420 / 40 | 21 | 3 | VECTOR_ONLY | 0.917 | 1.000 | 1.000 | 6.674 | 8.358 |
| sentence-transformers/all-MiniLM-L6-v2 | 420 / 40 | 21 | 3 | GRAPH_THEN_VECTOR | 1.000 | 1.000 | 1.000 | 6.122 | 7.344 |
| sentence-transformers/all-MiniLM-L6-v2 | 420 / 40 | 21 | 5 | VECTOR_ONLY | 0.800 | 1.000 | 1.000 | 7.969 | 8.837 |
| sentence-transformers/all-MiniLM-L6-v2 | 420 / 40 | 21 | 5 | GRAPH_THEN_VECTOR | 0.950 | 1.000 | 1.000 | 7.948 | 8.588 |
| sentence-transformers/all-MiniLM-L6-v2 | 420 / 40 | 21 | 10 | VECTOR_ONLY | 0.442 | 1.000 | 1.000 | 5.648 | 8.077 |
| sentence-transformers/all-MiniLM-L6-v2 | 420 / 40 | 21 | 10 | GRAPH_THEN_VECTOR | 0.525 | 1.000 | 1.000 | 5.669 | 8.226 |
| sentence-transformers/all-MiniLM-L6-v2 | 900 / 120 | 21 | 3 | VECTOR_ONLY | 0.917 | 1.000 | 1.000 | 6.344 | 7.907 |
| sentence-transformers/all-MiniLM-L6-v2 | 900 / 120 | 21 | 3 | GRAPH_THEN_VECTOR | 1.000 | 1.000 | 1.000 | 5.941 | 8.023 |
| sentence-transformers/all-MiniLM-L6-v2 | 900 / 120 | 21 | 5 | VECTOR_ONLY | 0.800 | 1.000 | 1.000 | 7.210 | 9.211 |
| sentence-transformers/all-MiniLM-L6-v2 | 900 / 120 | 21 | 5 | GRAPH_THEN_VECTOR | 0.950 | 1.000 | 1.000 | 5.959 | 8.226 |
| sentence-transformers/all-MiniLM-L6-v2 | 900 / 120 | 21 | 10 | VECTOR_ONLY | 0.442 | 1.000 | 1.000 | 8.427 | 8.670 |
| sentence-transformers/all-MiniLM-L6-v2 | 900 / 120 | 21 | 10 | GRAPH_THEN_VECTOR | 0.525 | 1.000 | 1.000 | 7.820 | 8.867 |
| sentence-transformers/all-MiniLM-L6-v2 | 1400 / 160 | 21 | 3 | VECTOR_ONLY | 0.917 | 1.000 | 1.000 | 7.015 | 7.920 |
| sentence-transformers/all-MiniLM-L6-v2 | 1400 / 160 | 21 | 3 | GRAPH_THEN_VECTOR | 1.000 | 1.000 | 1.000 | 6.486 | 7.842 |
| sentence-transformers/all-MiniLM-L6-v2 | 1400 / 160 | 21 | 5 | VECTOR_ONLY | 0.800 | 1.000 | 1.000 | 5.626 | 8.431 |
| sentence-transformers/all-MiniLM-L6-v2 | 1400 / 160 | 21 | 5 | GRAPH_THEN_VECTOR | 0.950 | 1.000 | 1.000 | 5.779 | 8.164 |
| sentence-transformers/all-MiniLM-L6-v2 | 1400 / 160 | 21 | 10 | VECTOR_ONLY | 0.442 | 1.000 | 1.000 | 5.805 | 8.684 |
| sentence-transformers/all-MiniLM-L6-v2 | 1400 / 160 | 21 | 10 | GRAPH_THEN_VECTOR | 0.525 | 1.000 | 1.000 | 5.714 | 7.676 |
| sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 420 / 40 | 21 | 3 | VECTOR_ONLY | 0.944 | 1.000 | 1.000 | 6.112 | 8.586 |
| sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 420 / 40 | 21 | 3 | GRAPH_THEN_VECTOR | 1.000 | 1.000 | 1.000 | 6.006 | 7.967 |
| sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 420 / 40 | 21 | 5 | VECTOR_ONLY | 0.750 | 1.000 | 1.000 | 6.724 | 8.069 |
| sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 420 / 40 | 21 | 5 | GRAPH_THEN_VECTOR | 0.950 | 1.000 | 1.000 | 6.706 | 9.153 |
| sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 420 / 40 | 21 | 10 | VECTOR_ONLY | 0.450 | 1.000 | 1.000 | 6.734 | 8.387 |
| sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 420 / 40 | 21 | 10 | GRAPH_THEN_VECTOR | 0.525 | 1.000 | 1.000 | 6.578 | 7.955 |
| sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 900 / 120 | 21 | 3 | VECTOR_ONLY | 0.944 | 1.000 | 1.000 | 5.407 | 7.938 |
| sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 900 / 120 | 21 | 3 | GRAPH_THEN_VECTOR | 1.000 | 1.000 | 1.000 | 5.355 | 7.173 |
| sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 900 / 120 | 21 | 5 | VECTOR_ONLY | 0.750 | 1.000 | 1.000 | 5.729 | 8.071 |
| sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 900 / 120 | 21 | 5 | GRAPH_THEN_VECTOR | 0.950 | 1.000 | 1.000 | 5.865 | 7.865 |
| sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 900 / 120 | 21 | 10 | VECTOR_ONLY | 0.450 | 1.000 | 1.000 | 5.760 | 8.367 |
| sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 900 / 120 | 21 | 10 | GRAPH_THEN_VECTOR | 0.525 | 1.000 | 1.000 | 5.742 | 7.902 |
| sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 1400 / 160 | 21 | 3 | VECTOR_ONLY | 0.944 | 1.000 | 1.000 | 5.766 | 7.921 |
| sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 1400 / 160 | 21 | 3 | GRAPH_THEN_VECTOR | 1.000 | 1.000 | 1.000 | 5.670 | 7.906 |
| sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 1400 / 160 | 21 | 5 | VECTOR_ONLY | 0.750 | 1.000 | 1.000 | 7.217 | 9.524 |
| sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 1400 / 160 | 21 | 5 | GRAPH_THEN_VECTOR | 0.950 | 1.000 | 1.000 | 7.527 | 10.558 |
| sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 1400 / 160 | 21 | 10 | VECTOR_ONLY | 0.450 | 1.000 | 1.000 | 6.168 | 7.074 |
| sentence-transformers/multi-qa-MiniLM-L6-cos-v1 | 1400 / 160 | 21 | 10 | GRAPH_THEN_VECTOR | 0.525 | 1.000 | 1.000 | 6.123 | 6.706 |

All numbers above are emitted by the evaluation program; none are hand-entered.
