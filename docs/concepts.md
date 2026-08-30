---
doc_id: motif-balance-concepts
title: Balanced motif design concepts
intent: Explain the problem, vocabulary, and evidence boundary.
audience:
  - new users
  - users
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-30
doc_type: explanation
---

# Balanced motif design concepts

A motif model is usually used to scan an existing DNA sequence for matching
windows. Motif Balance performs the inverse operation: given explicit motif
models and a fixed sequence length, it searches sequence space while allowing
the best-scoring word, placement, strand, and any shared coordinates for each
motif to emerge from the candidate sequence.

Evaluation finds one deterministic best match for every motif, reports each
best raw log-likelihood-ratio score as relative attainment between that motif's
theoretical minimum and maximum over one motif-width word, and takes the
weakest relative score. The public balance score is therefore:

```text
balance_score = min(per_motif_relative_attainments)
```

This max-min objective makes the bottleneck explicit: a candidate cannot look
strong merely because one motif scores very well while another scores poorly.

The method has three separate decisions:

1. **Evaluation** determines matches and scores for an immutable sequence.
2. **Search** proposes candidate sequences under explicit budgets.
3. **Selection** chooses an exact, optionally diverse portfolio from evaluated
   candidates.

Those separations prevent an optimizer surrogate or a diversity rule from
silently changing the public score. Both normalization endpoints are attainable
by individual motif-width words. After retaining the best score across multiple
placements or orientations, the upper endpoint remains attainable by embedding
a score-maximizing word, while the lower endpoint need not be attainable by the
sequence-level scan. A high relative attainment remains a model-relative
result, not proof of expression, binding, transferability, or experimental
success.

Complete enumeration establishes the optimum when the admitted sequence space
fits the declared evaluator budget. Larger spaces use bounded annealed search,
so their result is the best sequence observed under that budget rather than a
proof of convergence or global optimality. Overlapping representative windows
show that model-defined matches share candidate coordinates; they do not show
simultaneous motif occupancy, co-binding, or regulatory function.
