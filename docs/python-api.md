---
doc_id: motif-balance-python-tutorial
title: Design and inspect from Python
intent: Design DNA with source-attributed ArgR and Cra motif profiles.
audience: [new users, API consumers]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-26
doc_type: tutorial
---

# Design and inspect from Python

Run this from the [source checkout](installation.md#install-from-source) after
preparing the ArgR and Cra inputs during installation.
The prepared [ArgR and Cra inputs](../examples/argr-cra/README.md) contain nucleotide
probabilities prepared from Baumgart et al. (2021), Supplementary Data 2.
Each row lists the probabilities of A, C, G and T at one motif position.

```python
# Load the real motif models and request four 32-base sequences.
from pathlib import Path

from motif_balance import DesignSpec, MotifSpecification, design, score
from motif_balance.formats.motif import read_motif
from motif_balance.inspection import inspect_result
from motif_balance.inspection.render import render_candidate_svg, render_text

argr = read_motif("examples/argr-cra/inputs/motifs/argR.json")
cra = read_motif("examples/argr-cra/inputs/motifs/cra.json")
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

## Select different arrangements

Use the retained search pool to select two representatives with different site
orders, strand relationships, or overlaps. This rescoring step does not repeat
the search.

```python
from motif_balance.alternatives import rank_architectures

pool = tuple(item.sequence for item in portfolio.manifest.elites)
ranking = rank_architectures(pool, spec, grouping="interval_topology")
selected = ranking.select(2)
for representative in selected:
    print(representative.sequence, round(representative.balance_score, 3))
```

These two arrangements have balances of approximately 0.880 and 0.823.
`select(2)` requires two available classes; use `select_up_to(2)` when a smaller
collection is acceptable. See [collections](choose-alternatives.md) for the
arrangement definition and reported shortfalls.

## Vary a sequence within one selected arrangement

Now use the first representative as the parent. Diversification varies bases
within its desired sites while retaining each selected site's coordinates and
strand. Every motif's score is protected separately.

```python
from motif_balance.variants import diversify
from motif_balance.formats.variants import variants_fasta, variants_tsv

parent = selected[0]
library = diversify(parent.sequence, spec, max_score_loss=0.02, max_variants=256)
print(library.template, library.encoded_sequence_count)
print(library.minimum_balance, library.maximum_component_loss)
with Path("library.json").open("x") as output:
    output.write(library.model_dump_json(indent=2))
with Path("variants.fasta").open("x") as output:
    output.write(variants_fasta(library))
with Path("variant-scores.tsv").open("x") as output:
    output.write(variants_tsv(library))
```

For this ArgR/Cra parent, the operation returns eight sequences, with a minimum
balance of approximately 0.863 and a largest component loss below 0.02.
The ambiguity template describes exactly the concrete variants in the export.
Every combination is checked, including combinations of substitutions that pass
individually. A 0.02 tolerance permits two hundredths of loss on each model's
score scale. The cap includes the parent, and a parent-only result is possible.
See [diversification](diversify-sequences.md) for editable positions, unwanted
motifs, and the substitution map.

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
