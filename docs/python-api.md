# Design and inspect from Python

Start with the [README installation and input preparation](../README.md#1-install-and-prepare-the-profiles).
Run these examples in that same uv project.
The prepared [ArgR and Cra inputs](../examples/argr-cra/README.md) contain nucleotide
probabilities prepared from Baumgart et al. (2021), Supplementary Data 2.
Each row lists the probabilities of A, C, G and T at one motif position.
See [a prepared profile](motif-models.md#inspect-a-prepared-profile) for a compact
display of the Cra model.

```python
# Load the real motif models and request four 25-base sequences.
from pathlib import Path

from motif_balance import DesignSpec, MotifSpecification, design, score
from motif_balance.formats.motif import read_motif
from motif_balance.inspection import inspect_result
from motif_balance.inspection.render import render_candidate_svg, render_text

argr = read_motif("inputs/motifs/argR.json")
cra = read_motif("inputs/motifs/cra.json")
print(cra)                                               # Preview its probabilities
spec = DesignSpec(
    specifications=(
        MotifSpecification(motif=argr, direction="seek"),  # Strengthen the ArgR match
        MotifSpecification(motif=cra, direction="seek"),   # Strengthen the Cra match
    ),
    length=25,                                             # DNA length in base pairs
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

The run returns four sequences, with a best balance of approximately **0.855**.
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

These two arrangements have balances of approximately 0.855 and 0.801.
`select(2)` requires two available classes; use `select_up_to(2)` when a smaller
collection is acceptable. See [collections](choose-alternatives.md) for the
arrangement definition and reported shortfalls.

## Expand a selected arrangement into a sequence list

Use the first representative as the parent, retaining its selected motif sites
and requiring every sequence to have balance at least 0.8:

```python
from motif_balance.variants import expand, load_expansion

parent = selected[0]
expanded = expand(parent.sequence, spec, min_balance=0.8, max_variants=256)
print(len(expanded.variants), expanded.minimum_balance, expanded.stop_reason)
with Path("expansion.json").open("x") as output:
    output.write(expanded.model_dump_json(indent=2))
verified = load_expansion(Path("expansion.json").read_bytes())
```

This returns 256 sequences for the ArgR/Cra parent. The sequence cap includes
the parent; other requests can return fewer. These explicit alternatives need
not form a complete ambiguity template. See [expansion](expand-sequences.md)
for FASTA exports, whole collections, and evaluation limits.

## Construct a checked ambiguity template

For degenerate synthesis, `diversify` instead requires every combination in an
IUPAC template to pass. This example protects each motif's parental score
separately while preserving its selected site.

```python
from motif_balance.variants import diversify
from motif_balance.formats.variants import variants_fasta, variants_tsv

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

For this ArgR/Cra parent, the operation returns sixteen sequences, with a minimum
balance of approximately 0.838 and a largest component loss below 0.02.
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
file's directory. The [input reference](design-spec.md) lists the fields.

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
