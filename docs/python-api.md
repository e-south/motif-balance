---
doc_id: motif-balance-python-tutorial
title: Design and inspect from Python
intent: Design DNA with source-attributed ArgR and Cra motif profiles.
audience: [new users, API consumers]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-21
doc_type: tutorial
---

# Design and inspect from Python

Run this from the [source checkout](installation.md#install-from-source).
The [ArgR and Cra inputs](../examples/argr-cra/README.md) contain nucleotide
probabilities prepared from Baumgart et al. (2021), Supplementary Data 2.
Each row lists the probabilities of A, C, G and T at one motif position.

```python
# Load the real motif models and request four 32-base sequences.
from pathlib import Path

from motif_balance import DesignSpec, MotifSpecification, design, score
from motif_balance.formats.motif import read_motif
from motif_balance.inspection import inspect_result
from motif_balance.inspection.render import render_candidate_svg, render_text

argr = read_motif("examples/argr-cra/motifs/argR.json")
cra = read_motif("examples/argr-cra/motifs/cra.json")
spec = DesignSpec(
    specifications=(
        MotifSpecification(motif=argr, direction="seek"),  # Strengthen the ArgR match
        MotifSpecification(motif=cra, direction="seek"),   # Strengthen the Cra match
    ),
    length=32,                                             # DNA length in base pairs
    count=4,                                               # Returned sequences
    evaluations=4096,                                      # Candidate-evaluation budget
    seed=7,
)
portfolio = design(spec)                                   # Edit DNA and rescan both strands
candidate = portfolio.candidates[0]
evaluation = score(candidate.sequence, spec)               # Recompute its motif matches
for match in evaluation.matches:
    print(match.motif_id, match.spec_satisfaction)

# Save, verify and draw the result without repeating the search.
portfolio.write(Path("result"))                            # Use a new directory
review = inspect_result(Path("result"), kind="bundle")     # Check recorded sequences and scores
print(render_text(review))
with Path("candidate.svg").open("xb") as output:
    output.write(render_candidate_svg(review, candidate_rank=1))
```

The run returns four sequences, with a best balance of approximately **0.880**.
`candidate.svg` aligns the selected matches and motif logos on double-stranded
DNA. The score measures agreement with the supplied models.

## Compare search methods

Use the same motifs, length and evaluation budget to compare the three policies:

```python
# Compare policies on the same request and print each best balance.
for method in ("annealed", "greedy", "random"):
    result = design(spec, method=method)
    print(method, result.manifest.evaluation_count, result.manifest.best_observed.balance_score)
```

Annealed search combines several edit types and can accept worse states during
exploration. Greedy search accepts only improving single-base changes. Random
search draws independent sequences. [Methods](methods.md#explicit-comparison-methods)
defines their evaluation accounting and initialization.

## Reuse inputs and handle failures

For a YAML request, replace the request construction with
`spec = load_design_spec(Path("design.yaml"))`, importing `load_design_spec`
from `motif_balance.formats.design`. Relative model paths resolve against that
file's directory. The [input reference](design-spec.md) owns its exact fields.

`design` returns the requested count or raises a typed error; it does not return
a partial successful portfolio. `score` rejects wrong-length or ambiguous DNA
with `motif_balance.errors.InvalidSequence`. Invalid model/request construction
raises `pydantic.ValidationError`. Invalid publication raises
`motif_balance.errors.ArtifactError`.

Choose new output names before repeating the example: neither `Portfolio.write`
nor the exclusive SVG write replaces an existing destination. In Python, search
and publication are separate operations; a later write failure leaves the
computed portfolio in memory, so it can be written to a different destination
without another search.

Next: [assess a pair before searching](pair-assessment.md),
[choose architectures from a verified design](choose-alternatives.md#continue-from-a-saved-design),
[score an existing sequence](score-sequences.md),
[inspect a result](reference/result-inspection.md), or use the
[API reference](reference/public-contract.md) for advanced integration.
