---
doc_id: motif-balance-pair-assessment
title: Assess a motif pair before sequence search
intent: Explain and use length-aware shared-base conflict without predicting sequence scores or biology.
audience:
  - users
  - API consumers
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-10
doc_type: how-to
journey:
  - assess
---

# Assess a motif pair before sequence search

Two motif windows may need to share DNA positions. If their preferred bases
agree, sharing can be inexpensive; if they disagree, a short sequence may force
a compromise. More length can permit separation. `assess_pair` calculates this
local preference conflict across the allowed arrangements, before generating
any candidate sequences.

Use it to inspect a request's motif-level constraints and compare length
choices. It returns a **structural score**, not a predicted optimization score,
binding probability, or proof that the requested sequence can attain that score.
Here, structural means motif-column arrangement, not molecular structure.

The API and command are unreleased: use the current source-checkout installation in
the [quickstart](quickstart.md#install), or a verified build containing this API.
A package version label alone does not establish that an older wheel contains
it.

## Assess two files from the terminal

From the source checkout, use the two canonical models already supplied with
the synthetic example:

```bash
uv run motif-balance assess \
  examples/synthetic-pairwise/motifs/motif-a.yaml \
  examples/synthetic-pairwise/motifs/motif-b.yaml \
  --length 2 --strands both
```

These models prefer AC and GT. Their structural score is 1 because reverse
complementation makes their preferred words agree. The summary identifies the
input models, length/strand assumptions, relative arrangement, and zero sequence
evaluations. It does not generate a sequence or claim biological compatibility.

Use `--format json` for every arrangement and input-model digest. Add
`--out assessment.json` to write that JSON into a new file; omit `--out` to
print it. Existing files, directories, and symlinks are never replaced, including
an output created by another caller during calculation. The parent directory
must exist. No format creates a result bundle or alters its inputs.

Use `--format svg --out preferences.svg` to see the best relative arrangement as
aligned information logos. Both logos use the top-strand coordinate frame;
reverse-strand preferences are complemented once. Shaded columns and symbols
distinguish positive from zero local conflict. These are **model preferences
before sequence search**, not a designed sequence or selected binding sites.
There is deliberately no duplex sequence or observed-base coloring in this view.
The score favors less conflict; logo height shows information in bits, not regret.

Inputs must be single canonical YAML/JSON `motif-model/v2` records with
explicit backgrounds. A MEME database or raw count file is not silently reduced
to its first motif; [prepare the model explicitly](motif-models.md) first.
Malformed models, symlink inputs, invalid lengths/strands, and operation-limit
refusals return exit code 2. `--debug` exposes the underlying exception; ordinary
errors explain the correction without a traceback.

## Try an agreement-versus-conflict example in Python

Run this Python example from any directory; it needs no database,
study files, or search configuration.
The synthetic models prefer AAA and CCC; their equal-strength preferences
conflict at every shared position.

```python
from motif_balance import MotifModel
from motif_balance.assessment import assess_pair

left = MotifModel(
    motif_id="left",
    probabilities=((0.7, 0.1, 0.1, 0.1),) * 3,
    background=(0.25, 0.25, 0.25, 0.25),
)
right = MotifModel(
    motif_id="right",
    probabilities=((0.1, 0.7, 0.1, 0.1),) * 3,
    background=(0.25, 0.25, 0.25, 0.25),
)
for length in range(3, 7):
    result = assess_pair(left, right, length=length, strands="both")
    print(
        f"{length} nt: structural score {result.structural_score:.3f}; "
        f"{result.arrangement_count} relative arrangements"
    )
best = result.best_arrangement
print(
    f"Best at 6 nt: left {best.left_start} {best.left_strand}; "
    f"right {best.right_start} {best.right_strand}"
)
print("Sequence evaluations:", result.sequence_evaluations)
```

The scores are 0.500, 0.667, 0.833, and 1.000 at 3–6 nt. At six bases, a
nonoverlapping arrangement removes this pair's local conflict. For agreement,
replace the right matrix with the left matrix: the shared AAA preference costs
nothing. Reversing a motif can also relieve conflict—for example, the reverse
complement of a TTT preference is AAA. The calculation checks both relative
strand choices when `strands="both"`; it does not select a convenient alignment
to label compatible while ignoring the others.

## Read the returned profile

The explicit Python seam is
`motif_balance.assessment.assess_pair(left, right, *, length, strands="both")`.
Both arguments are current `MotifModel` values. They represent two desired
motifs; this operation does not accept avoidance requirements or larger sets.
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

This is a sum of local compromises, not the whole-motif hard-minimum objective
used by [sequence scoring](score-sequences.md). It enumerates relative
arrangements and four base choices, not the `4^length` sequence space. It is a
smaller deterministic minimization, not an absence of optimization altogether.

Increasing length expands the allowed seek-pair arrangements, so the best
structural score cannot decrease. It can reach a ceiling when separation fits;
that ceiling no longer distinguishes requests, while finite-budget search
outcomes can still differ. A value of 0.9 does not forecast balance 0.9. Numerical
prediction, ranking performance, and transfer to new model collections require
caller-owned evaluation. Avoidance and higher-cardinality behavior do not inherit
any seek-pair interpretation.

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

Next: [design and inspect sequences](python-api.md), or compare their actual
[recovered quality and alternatives](interpreting-results.md).
