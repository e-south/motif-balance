---
doc_id: motif-balance-concepts
title: Balanced motif design concepts
intent: Explain the problem, vocabulary, and evidence boundary.
audience:
  - new users
  - users
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
doc_type: explanation
---

# Balanced motif design concepts

A motif model assigns a score to each possible placement of a motif in a DNA
sequence. Motif Balance finds the single declared best match for every motif,
reports each best raw log-likelihood-ratio score as relative attainment between
that motif's attainable score minimum and maximum, and optimizes the weakest
relative score. The public balance score is therefore:

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
silently changing the public score. A high relative attainment remains model-relative
result, not proof of expression, binding, transferability, or experimental
success.
