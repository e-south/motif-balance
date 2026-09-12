---
doc_id: motif-balance-concepts
title: Balanced motif design concepts
intent: Explain the problem, vocabulary, and evidence boundary.
audience:
  - new users
  - users
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-08
doc_type: explanation
---

# Balanced motif design concepts

A motif model is usually used to scan an existing DNA sequence for matching
windows. Motif Balance performs the inverse operation: given explicit motif
models and a fixed sequence length, it searches sequence space while allowing
the best-scoring word, placement, strand, and any shared coordinates for each
motif to emerge from the candidate sequence.

## One objective for desired and unwanted matches

Evaluation finds each motif's strongest match anywhere on the allowed strands.
Its raw log-odds score is normalized to that model's theoretical range over
one motif-width word. This is **attainment**, not a binding probability.

For the current directional contract, **satisfaction** is attainment for a
`seek` requirement and one minus attainment for an `avoid` requirement.
The public balance is the weakest satisfaction:

```text
satisfaction = attainment          # seek
satisfaction = 1 - attainment      # avoid
balance_score = min(specification_satisfactions)
```

This max-min objective makes the bottleneck explicit: a candidate cannot look
strong merely because one requirement scores very well while another is weak.
For two desired motifs, attainments (0.9, 0.5) give balance 0.5; (0.7, 0.7)
give a better balance of 0.7. If a desired motif attains 0.8 and an unwanted
motif's strongest match attains 0.3, their satisfactions are (0.8, 0.7) and
balance is 0.7. These are arithmetic examples, not biological thresholds.

Avoidance must consider the strongest unwanted match across the sequence.
Making one window weak does not suffice if another window still matches well.
A soft avoid direction is not a guarantee of exclusion below a hard threshold;
the [explicit hard-ceiling contract](design-spec.md#hard-avoidance-constraints)
has different semantics and is never silently substituted.

## One result, separate decisions

The method has three separate decisions:

1. **Evaluation** determines matches and scores for an immutable sequence.
2. **Search** proposes candidate sequences under explicit budgets.
3. **Selection** chooses an exact, optionally diverse portfolio from evaluated
   candidates.

Those separations prevent an optimizer surrogate or a diversity rule from
silently changing the public score. The portfolio's distance rule selects
alternatives; it does not estimate how many good sequences exist. Bounded
[quality samples](reference/search-observations.md#alternatives-at-declared-quality)
are available to callers that need further analysis. Comparing lengths,
independent searches, or motif sets remains a caller-owned experiment.

## What the scores do not establish

Both normalization endpoints are attainable
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
