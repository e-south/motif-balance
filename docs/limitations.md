---
doc_id: motif-balance-limitations
title: Motif Balance limitations
intent: Bound software claims and identify unsupported uses.
audience:
  - users
  - integrators
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
doc_type: explanation
---

# Motif Balance limitations

- Results are conditional on the supplied motif models, background,
  normalization, strand policy, and sequence constraints.
- A motif score is not a calibrated probability of binding or expression unless
  an external validation establishes that interpretation.
- Balancing model scores does not account for synthesis, genomic context,
  chromatin, RNA structure, off-target motifs, toxicity, or assay noise unless
  those constraints are modeled explicitly by a future version.
- A bounded stochastic search does not prove global optimality. Completion and
  budget status must be read with every portfolio.
- Diversity in sequence space does not imply mechanistic or biological
  diversity.
- One successful context does not establish cross-context portability.

Benchmark cohorts, controls, repetitions, statistical decisions, and claims
belong to the workflow consuming verified outputs. They are not inferred by
the package.
