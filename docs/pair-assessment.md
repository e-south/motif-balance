---
doc_id: motif-balance-pair-assessment
title: Assess a motif pair before sequence search
intent: Explain and use length-aware shared-base conflict without predicting sequence scores or biology.
audience: [users, API consumers]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-21
doc_type: how-to
journey: [assess]

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

Use the current [source installation](installation.md) or a build containing
this API.

## Assess two files from the terminal

From the source checkout, use the two canonical models already supplied with
the synthetic example:

```bash
# Compare the two motifs at the requested length before searching DNA.
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
# Import the models and operations used in this example.
from motif_balance import MotifModel
from motif_balance.assessment import assess_pair

# Define the first motif and its probability preferences.
left = MotifModel(
    motif_id="left",
    probabilities=((0.7, 0.1, 0.1, 0.1),) * 3,
    background=(0.25, 0.25, 0.25, 0.25),
)
# Define the second motif with different preferences at shared positions.
right = MotifModel(
    motif_id="right",
    probabilities=((0.1, 0.7, 0.1, 0.1),) * 3,
    background=(0.25, 0.25, 0.25, 0.25),
)
# Compare permitted overlaps as the DNA length increases.
for length in range(3, 7):
    result = assess_pair(left, right, length=length, strands="both")
    print(
        f"{length} nt: structural score {result.structural_score:.3f}; "
        f"{result.arrangement_count} relative arrangements"
    )
# Read the least-conflicting arrangement at the last tested length.
best = result.best_arrangement
# Print its displacement, orientation and shared span.
print(
    f"Best at 6 nt: left {best.left_start} {best.left_strand}; "
    f"right {best.right_start} {best.right_strand}"
)
# Confirm that assessment did not evaluate candidate DNA sequences.
print("Sequence evaluations:", result.sequence_evaluations)
```

The scores are 0.500, 0.667, 0.833, and 1.000 at 3–6 nt. At six bases, a
nonoverlapping arrangement removes this pair's local conflict. For agreement,
replace the right matrix with the left matrix: the shared AAA preference costs
nothing. Reversing a motif can also relieve conflict: the reverse complement of a TTT
preference is AAA. The calculation checks both relative
strand choices when `strands="both"`; it does not select a convenient alignment
to label compatible while ignoring the others.

## Calculation and reference

See [pair and joint assessment reference](reference/pair-assessment.md) for definitions, formulas, returned fields,
resource limits and verification.
