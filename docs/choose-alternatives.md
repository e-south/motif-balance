---
doc_id: motif-balance-choose-alternatives
title: Choose alternative motif architectures
intent: Rank supplied sequences by distinct selected-match architecture and inspect every supported collection size.
audience: [users, API consumers]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-21
doc_type: how-to
journey: [integrate]

---

# Choose alternative motif architectures

A collection contains sequences whose selected motif matches have different
arrangements. `rank_architectures` keeps the best sequence for each arrangement
and orders those representatives by balance. It selects from supplied sequences
without running another search.

| Choice | When to use it |
| --- | --- |
| `grouping="interval_topology"` | Compare motif order, strand, gaps, overlap and containment |
| `grouping="exact_offsets"` | Also distinguish exact spacing between matches; the Python default |
| `select(K)` | Require exactly K available arrangements |
| `select_up_to(K)` | Return the available arrangements and report any shortfall |

An arrangement uses each motif's selected strongest match. Moving the complete
duplex does not create another arrangement. With both-strand scanning, reversing
the complete duplex is also equivalent. The [grouping reference](reference/architecture-ranking.md#what-counts-as-an-architecture)
defines how ties and interval endpoints are handled.

To select from a saved design at the terminal:

```bash
# Select up to eight distinct arrangements from the result's retained search pool.
motif-balance collect architecture-result --count 8 --format json
```

The command reports how many arrangements were requested, available and delivered.
Use a design without a positive `min_distance`: arrangement grouping does not
enforce sequence separation. For a fixed-size set with explicit distance
requirements, use [portfolio selection](reference/portfolio-selection.md).

## Try a small supplied pool

Run this example from any directory. The two synthetic motifs prefer AA and
CC. The supplied AACC and CCAA sequences satisfy both with different orders;
ACAC supplies a third selected architecture at lower quality.

```python
# Import the models and operations used in this example.
from motif_balance import DesignSpec, MotifModel, MotifSpecification
from motif_balance.alternatives import rank_architectures

# Define a motif that prefers AA.
left = MotifModel(
    motif_id="left",
    probabilities=((0.7, 0.1, 0.1, 0.1),) * 2,
    background=(0.25, 0.25, 0.25, 0.25),
)
# Define a motif that prefers CC.
right = MotifModel(
    motif_id="right",
    probabilities=((0.1, 0.7, 0.1, 0.1),) * 2,
    background=(0.25, 0.25, 0.25, 0.25),
)
# Use four bases and forward scanning so motif order is easy to compare.
spec = DesignSpec(
    schema_version="design-spec/v3",
    specifications=(
        MotifSpecification(motif=left, direction="seek"),
        MotifSpecification(motif=right, direction="seek"),
    ),
    length=4,
    count=1,
    strands="forward",
    seed=7,
    evaluations=1,
)
# Supply sequences with different orders and match qualities.
sequences = ("AACC", "CCAA", "ACAC", "CACA", "AAAA", "CCCC")
# Keep the best sequence for each distinct motif arrangement.
ranking = rank_architectures(sequences, spec, grouping="interval_topology")
# Ask for up to eight arrangements, allowing an explicit shortfall.
collection = ranking.select_up_to(8)
# Check how many of the requested arrangements were actually available.
assert collection.requested_count == 8 and collection.delivered_count == 3
# Check that the result reports the shortfall.
assert collection.status == "insufficient_retained_architectures"
# Show the weakest balance retained as collection size increases.
for point in ranking.prefixes:
    print(
        f"{point.architecture_count} architecture(s): minimum balance {point.minimum_balance:.3f}"
    )
# Select exactly two arrangements from this pool.
selected = ranking.select(2)
# Print their sequences.
print("Selected:", ", ".join(item.sequence for item in selected))
# Separate the cost of rescoring the pool from any new search.
print(
    f"Sequence evaluations: {ranking.scoring_evaluations}; "
    f"search evaluations: {ranking.search_evaluations}"
)
```

The three prefix scores are 1, 1, and 0.5. `select(2)` returns AACC and CCAA
as immutable evaluations with their matches and directional scores. Requesting
four architectures with `select(4)` fails: these supplied sequences support only
three. `select_up_to(8)` instead returns those three with explicit shortfall and
weakest quality 0.5. That does not prove a fourth is impossible. A partial
collection's quality is the quality of its delivered members, not an absent Q8.

<details>
<summary>Continue from a saved design</summary>

## Continue from a saved design

Append this to the example above. First assess the same pair and length without
searching; then enumerate the small four-base space, save and inspect the result,
and select architectures from its retained sequences. The extra bases permit AA
and CC to sit separately. The structural score describes that lack of local
conflict; enumeration, not the descriptor, establishes the attainable score here.

```python
# Import the models and operations used in this example.
from pathlib import Path

from motif_balance import design
from motif_balance.artifacts import read_verified_portfolio
from motif_balance.assessment import assess_pair
from motif_balance.inspection import inspect_result
from motif_balance.inspection.render import render_text

# Assess shared-base preferences without searching for DNA.
assessment = assess_pair(left, right, length=spec.length, strands=spec.strands)
# Print the pre-search descriptor.
print(f"Pre-search structural score: {assessment.structural_score:.3f}")
# Allow all 256 four-base sequences to be evaluated.
search_spec = DesignSpec.model_validate({**spec.model_dump(mode="python"), "evaluations": 256})
# Generate sequences with that expanded budget.
portfolio = design(search_spec)
# Choose a new directory for the saved search.
destination = Path("architecture-result")
# Save the result and its inputs together.
portfolio.write(destination)
# Retain the identity of the result just produced.
expected_id = portfolio.manifest.bundle_id
# Verify the saved result against that identity.
review = inspect_result(destination, kind="bundle", expected_bundle_id=expected_id)
# Print the verified search summary.
print(render_text(review))

# Load the verified inputs and retained sequences.
saved = read_verified_portfolio(destination, expected_bundle_id=expected_id)
# Use the full retained pool, rather than only the returned winner.
pool = tuple(item.sequence for item in saved.manifest.elites)
# Group and rank the recovered motif arrangements.
recovered = rank_architectures(pool, saved.spec, grouping="interval_topology")
# Print the best two distinct arrangements.
print("Recovered alternatives:", ", ".join(item.sequence for item in recovered.select(2)))
# Report search evaluations separately from collection rescoring.
print(
    f"Search calls: {saved.manifest.evaluation_count}; "
    f"ranking calls: {recovered.scoring_evaluations}"
)
```

Expected: AACC and CCAA, each with balance 1. The ordinary portfolio contains
one sequence because `count=1`; the retained archive has all 256 sequences in
this tiny exhaustive example. Ranking re-scores that archive rather than
mistaking the selected portfolio for the search pool. It makes 256 additional
scoring calls but performs no new search. Inspection and verified loading also
replay stored scores; the printed counts are not an end-to-end compute total.
Large bounded runs retain a capped
archive, not every evaluated sequence; their recovered architecture count is
not the number intrinsically possible.

Use `read_verified_portfolio` to recover both the original inputs and the saved
pool. It checks file digests and replays scores. If you retained the bundle ID
from its producer, pass it as `expected_bundle_id` to check the result's identity
too. Choose a new destination before rerunning the example.

</details>

<details>
<summary>Draw a ranked alternative</summary>

## Inspect a ranked alternative

Append this to the first supplied-pool example; the saved-design example is
not required. Inspect the second architecture, CCAA, with the same duplex,
filled windows and aligned information logos used for ordinary result review.
The first architecture is AACC: both score one, but their selected motif order
differs. The rank below comes from the explicit ranking, not from a run winner.

```python
# Import the models and operations used in this example.
from motif_balance import Candidate
from motif_balance.inspection import inspect_candidate
from motif_balance.inspection.render import render_candidate_svg
from motif_balance.model import candidate_id_for_sequence

# Choose the second ranked arrangement for illustration.
representative = ranking.representatives[1]
# Attach its selected rank and sequence identity to the scored candidate.
candidate = Candidate(
    candidate_id=candidate_id_for_sequence(representative.evaluation.sequence),
    rank=representative.rank,
    **representative.evaluation.model_dump(mode="python"),
)
# Rescore the candidate and project its motif matches for inspection.
candidate_review = inspect_candidate(candidate, ranking.spec)
# Render those matches as a duplex with aligned logos.
svg = render_candidate_svg(candidate_review)
# Keep the corresponding numeric inspection record.
review_json = candidate_review.model_dump_json(indent=2)
# Print which ranked candidate the figure represents.
print(f"Inspected supplied rank {candidate.rank}: {candidate.sequence}")
```

`svg` is UTF-8 SVG bytes and `review_json` contains the numeric projection.
Inspection performs one additional score replay; rendering performs none.
Neither writes files, searches, reorders the collection, or verifies its source
history. The SVG explicitly labels this as a caller-supplied rank. Keep your
source and selection receipts separately; see the
[inspection contract](reference/result-inspection.md#inspect-a-supplied-candidate)
for validation and rendering limits.

</details>

## Calculation and reference

See [architecture grouping and ranking](reference/architecture-ranking.md) for definitions, formulas, returned fields,
resource limits and verification.
