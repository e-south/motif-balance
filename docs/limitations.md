---
doc_id: motif-balance-limitations
title: Motif Balance limitations
intent: Bound software claims and identify unsupported uses.
audience:
  - users
  - integrators
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-08
doc_type: explanation
---

# Motif Balance limitations

- Results are conditional on the supplied motif models, background,
  normalization, strand policy, and sequence constraints.
- A motif score is not a calibrated probability of binding or expression unless
  an external validation establishes that interpretation.
- Balancing model scores does not account for synthesis, genomic context,
  chromatin, RNA structure, toxicity, or assay noise.
- Directional `avoid` satisfaction weakens the strongest sequence-wide model
  match while trading off against other requirements. It does not enforce a
  hard threshold or establish biological off-target specificity. Explicit
  legacy hard-ceiling requests have different feasibility semantics.
- Shared coordinates between representative motif windows do not establish
  simultaneous occupancy, co-binding, or regulatory function.
- A bounded stochastic search does not prove global optimality. Completion and
  budget status must be read with every portfolio; only complete enumeration
  over the admitted sequence space establishes an optimum.
- Reaching the bounded distance-selection node limit leaves feasibility
  unresolved; it is not evidence that no valid portfolio exists.
- Diversity in sequence space does not imply mechanistic or biological
  diversity. Selected portfolios and bounded quality samples are recovered
  alternatives, not uniform samples or estimates of total solution-space volume.
- One successful context does not establish cross-context portability.

Benchmark cohorts, controls, repetitions, statistical decisions, and claims
belong to the workflow consuming verified outputs. They are not inferred by
the package.
