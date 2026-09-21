---
doc_id: motif-balance-assessment-reference
title: Pair and joint assessment reference
intent: Define the calculation, returned records and validation limits.
audience: [API consumers]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-20
doc_type: reference
---

# Pair and joint assessment reference

## Read the returned profile

The explicit Python interface is
`motif_balance.assessment.assess_pair(left, right, *, length, strands="both")`.
Both arguments are current `MotifModel` values. They represent two desired
motifs; this pair profile does not accept avoidance requirements or larger sets.
Use the bounded joint operation below for three or four desired motifs.
No seed, search budget, candidate count, filesystem path, or optimized sequence
is an assessment input.

For the molecular diagram, construct
`motif_balance.inspection.assessment.inspect_pair_assessment(left, right, length=length)`
and pass it to `motif_balance.inspection.render.render_pair_assessment_svg`.
The inspector computes the assessment and its per-coordinate base regrets from
the supplied models; the renderer only presents that immutable projection.
`model_dump_json()` retains the inspection, including model probabilities, so
the caller must respect source rights before sharing it. Ordinary assessment
JSON does not include the probabilities. Rendered SVG uses Arial labels and
Arial Bold information glyphs without an external font or renderer dependency.

| Result | Meaning |
| --- | --- |
| `structural_score` | Highest local-conflict score among the allowed relative arrangements. |
| `best_arrangement` | One deterministic best placement: zero-based starts, strands, overlap, and score. |
| `arrangements` | Every allowed relative arrangement and its score, in fixed strand/offset order—not score order. |
| `motifs` | Input model IDs, content digests, widths, and indices of zero-range columns. |
| `length`, `strands`, `equivalence` | The space and symmetry assumptions used in the calculation. |
| `effective_information_bits` | Information remaining after zero-range columns receive zero weight. |
| `base_operation_upper_bound` | Conservative count of compared base preferences; not CPU instructions or wall time. |
| `sequence_evaluations` | Zero: this operation does not generate or score complete DNA sequences. |

Moving both motifs together does not change local conflict, so global
translations are counted once. With both strands, global reverse complements
are also counted once by fixing the left motif's strand to `+`. The right motif
can be `+` or `-`. Coordinates are relative to the first occupied base; they are
not a proposed unique location within a longer construct.

These are **labeled relative arrangements**, not the absolute placement count,
selected-match architectures of searched sequences, or distinct functional
designs. Palindromic motifs still retain their labeled relative strand choices.
The best tie breaks by left start, right start, then `+` before `-`; motif order
identifies the two input roles. Swapping roles preserves the best score but can
change its representative coordinates and ordering.

Inspect the complete profile when one best arrangement hides differences in
the other arrangements. A broad favorable profile is a possible explanation
for alternative designs, not an established predictor of recovered diversity.
It does not count sequences, resolve tied strongest sites in a sequence, or
measure how far apart designs are.

## What the score calculates

The independently identified formula is
`information_weighted_shared_base_conflict_v1` in `pair-assessment/v1`:

1. Use each model's compiled log-odds against its declared background.
2. Scale each column's least-to-most preferred base from zero to one.
3. Weight the column by `1 − H/2`, where H is its base-2 probability entropy.
   This information reference is uniform, even for nonuniform scoring backgrounds.
   A column with exactly zero log-odds range receives **zero weight**: it has no
   base preference to conflict with another column.
4. For each arrangement and shared coordinate, choose the base minimizing the
   sum of weighted preference shortfalls. Sum across shared coordinates, divide
   by total effective weight, and subtract from one.

This is a sum of local compromises, not the whole-motif minimum objective
used by [sequence scoring](../score-sequences.md). It enumerates relative
arrangements and four base choices, not the `4^length` sequence space. It is a
smaller deterministic minimization, not an absence of optimization altogether.

Increasing length expands the allowed seek-pair arrangements, so the best
structural score cannot decrease. It can reach a ceiling when separation fits;
that ceiling no longer distinguishes requests, while finite-budget search
outcomes can still differ. A value of 0.9 does not forecast balance 0.9. Numerical
prediction, ranking performance, and transfer to new model collections require
evaluation on the intended model collection. Avoidance and higher-cardinality behavior do not inherit
any seek-pair interpretation.

## Joint assessment of two to four motifs

`assess_motifs(models, *, length, strands="both")` extends the same local-regret
formula to a tuple of two to four validated models with distinct motif IDs.
It sums **all** participating column regrets at each coordinate before choosing
the best base. Pairwise agreement does not guarantee joint agreement: three
one-column preferences allowing AC, CG and AG each have a shared preferred
base with either other model, yet no base satisfies all three.

```python
from motif_balance import MotifModel
from motif_balance.assessment import assess_motifs

models = tuple(
    MotifModel(
        motif_id=f"model-{i}",
        probabilities=(tuple(0.4 if b in allowed else 0.1 for b in "ACGT"),),
        background=(0.25,) * 4,
    )
    for i, allowed in enumerate(("AC", "CG", "AG"))
)
assessment = assess_motifs(models, length=1, strands="forward")
assert abs(assessment.structural_score - 2 / 3) < 1e-12
print(assessment.proof, assessment.best_arrangement)
```

For files, keep the two positional inputs and append `--additional third.json`,
optionally `--additional fourth.json`, to `motif-balance assess`. Text and JSON
support the joint operation; SVG remains a pair inspection. The existing
no-additional-model command still returns `pair-assessment/v1`.

`joint-assessment/v1` binds all model digests, length, strand policy, operation
bound and the number of arrangements examined. It returns one best arrangement
with `starts` and `strands` in input order. Ties use lowest local loss, then the
lexicographically smallest starts and strands. JSON validation checks scope and
placement consistency; it cannot certify externally altered scores. Recompute
from the identified models to verify them.

Joint assessment is exact within its admitted arrangement space; its proof is
`exact_minimum_over_admitted_arrangements`. This is an optimum of the local-regret
descriptor, **not** of balanced sequence scoring. There is no approximate fallback.
Requests exceeding 100,000 arrangements or 20,000,000 base preference operations
are refused before compiling matrices. Work is bounded independently of search.
Only the best arrangement is retained, so a joint result is not an arrangement
breadth profile. Larger sets and avoidance remain unsupported by this assessment.

For widths w_i, define p_i = length − w_i + 1. Translation normalization leaves
`product(p_i) − product(p_i − 1)` placements: at least one start must be zero.
Forward-only requests have one orientation; both-strand requests have
`2^(motif_count − 1)` relative orientations because the first motif can be fixed
forward by permitted duplex reversal. Complete windows must fit within the
length. Labeled palindromic orientations remain distinct. The conservative
work bound is `4 × [sum(widths) + arrangements × (sum(widths) + length)]`.
No motifs are permuted or interchanged to reduce work.

## Limits and failures

`length` must be a native integer, at least the wider motif and at most 10,000.
Only `"forward"` and `"both"` are accepted. The operation admits at most
10,000,000 compared base preferences before compiling matrices or allocating
arrangements. A wider/longer request is rejected, not silently truncated.

The SVG view supports at most 128 nt and uniform scoring backgrounds, matching
the standard 0–2-bit information-logo convention. It refuses unsupported views
instead of truncating them or changing their background. Use the text/JSON
assessment for longer requests or nonuniform backgrounds. Structural validation
of an inspection catches identity, placement and score-total inconsistencies;
it is not an independent replay of externally edited per-base regrets. Rebuild
the inspection from the explicit models before trusting external data.

Invalid requests raise `motif_balance.errors.IncompatibleDesign` with an
explanation. Non-finite compiled log-odds, a motif without an attainable score
range, or a pair without positive effective information are also rejected.
Uniform-probability columns can have log-odds variation under a nonuniform
background but zero information under this descriptor; zero total weight is
undefined, not perfect compatibility.

The immutable result validates dimensions, full relative-placement coverage,
counts, and best-arrangement consistency. `model_dump_json()` exports its record;
`PairAssessment.model_validate_json(...)` checks that structure, **not** the
scientific correctness of externally modified scores. Recompute from the
identified motif models before trusting an external assessment. No assessment
is inserted into a search bundle, and this API performs no writes or network
access. The CLI uses this same API and scientific contract; text, JSON and SVG are
presentations of one assessment, not separate calculations.

Next: [design and inspect sequences](../python-api.md), or compare their actual
[recovered quality and alternatives](../interpreting-results.md).
