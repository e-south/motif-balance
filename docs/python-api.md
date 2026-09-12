---
doc_id: motif-balance-python-tutorial
title: Design and inspect from Python
intent: Complete a first design with inline synthetic inputs and no checkout-local files.
audience:
  - new users
  - API consumers
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-09
doc_type: tutorial
---

# Design and inspect from Python

Use this example after [installing the package](quickstart.md#install).
It works from an empty working directory; no motif database, repository examples,
or study environment is needed. Save the code as `first_design.py` and run it
with the Python interpreter in that environment.

The two synthetic motifs prefer AC and GT. In two DNA bases their preferences
must compete: AT attains half of each model's available score range. Complete
enumeration of all 16 sequences establishes that 0.5 is the best possible
weakest-motif satisfaction for this forward-only request.

```python
from pathlib import Path

from motif_balance import DesignSpec, MotifModel, MotifSpecification, design, score
from motif_balance.inspection import inspect_result
from motif_balance.inspection.render import render_candidate_svg, render_text

motif_a = MotifModel(
    schema_version="motif-model/v2",
    motif_id="motif_a",
    probabilities=((0.7, 0.1, 0.1, 0.1), (0.1, 0.7, 0.1, 0.1)),
    background=(0.25, 0.25, 0.25, 0.25),
)
motif_b = MotifModel(
    schema_version="motif-model/v2",
    motif_id="motif_b",
    probabilities=((0.1, 0.1, 0.7, 0.1), (0.1, 0.1, 0.1, 0.7)),
    background=(0.25, 0.25, 0.25, 0.25),
)
spec = DesignSpec(
    schema_version="design-spec/v3",
    specifications=(
        MotifSpecification(motif=motif_a, direction="seek"),
        MotifSpecification(motif=motif_b, direction="seek"),
    ),
    length=2,
    count=3,
    evaluations=16,
    seed=7,
    strands="forward",
    min_distance=0.25,
)
evaluation = score("AT", spec)
print("AT balance:", evaluation.balance_score)
for match in evaluation.matches:
    print(match.motif_id, match.spec_direction, match.spec_satisfaction)

portfolio = design(spec)
portfolio.write(Path("result"))
review = inspect_result(Path("result"), kind="bundle")
print(render_text(review))
with Path("candidate.svg").open("xb") as output:
    output.write(render_candidate_svg(review, candidate_rank=1))
```

Expected: `AT balance: 0.5`, three returned sequences, an exhaustive search,
and a verified `result/` bundle. `candidate.svg` shows the selected matches;
the terminal output supplies the summary without needing a browser.
The matrix rows are positions and the columns are A, C, G, T.

## Change one requirement

Set one specification's `direction` to `"avoid"` to make a weak strongest
match desirable. Its satisfaction is `1 - attainment`; this is soft avoidance,
not a hard exclusion threshold. Increasing `length` changes available space;
increasing `evaluations` changes search effort. Neither guarantees biological
function. See [concepts](concepts.md) before comparing their scores.

## Compare search methods explicitly

Append this to the example to try the same six-base problem with three methods:

```python
comparison_spec = DesignSpec.model_validate(
    {
        **spec.model_dump(mode="python"),
        "length": 6,
        "count": 1,
        "min_distance": 0.0,
        "evaluations": 127,
    }
)
for method in ("annealed", "greedy", "random"):
    result = design(comparison_spec, method=method)
    print(
        result.manifest.search_engine,
        result.manifest.evaluation_count,
        result.manifest.best_observed.balance_score,
    )
```

Each uses 127 scoring calls and the same motif objective. Annealed search uses
several edit types and can accept worse states; greedy search tries single-base
changes and adopts only strict improvement; random sampling draws independent
whole sequences. This one-seed example teaches the interface, not which method
is generally better. [Methods](methods.md#explicit-comparison-methods) explains
initialization, plateau behavior, and exact-versus-random semantics.

## Reuse inputs and handle failures

For a YAML request, replace the inline construction with
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
