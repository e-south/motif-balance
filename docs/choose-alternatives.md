---
doc_id: motif-balance-choose-alternatives
title: Choose alternative motif architectures
intent: Rank supplied sequences by distinct selected-match architecture and inspect every supported collection size.
audience: [users, API consumers]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-20
doc_type: how-to
journey: [integrate]

---

# Choose alternative motif architectures

Finding one good sequence does not tell you whether other useful arrangements
remain. `rank_architectures` scores a supplied sequence pool, keeps its best
representative of each selected-match architecture, and ranks those
representatives by quality. Choose the collection size you need and inspect
the weakest score retained. The operation selects from the supplied sequences without running another search.

If you instead need a fixed-size set satisfying hard footprint-separation and
architecture requirements, use [portfolio selection](reference/portfolio-selection.md).
That operation uses the unpruned sequence pool; architecture-rank prefixes are
diagnostics, not substitutes for a constrained portfolio.

Use `grouping="interval_topology"` for collections distinguished by motif order,
orientation and interval relationships. Exact gaps and overlap lengths remain
in every candidate's matches. This deliberately groups spacing variation within
one relationship; it does not assert that spacing is biologically unimportant.
The original Python default, `grouping="exact_offsets"`, remains available for
spacing-sensitive inspection. The grouping is recorded in the result.

Use the current [source installation](installation.md) or a build containing
these APIs.
The `collect` command selects from a verified saved design's retained elites:

```bash
motif-balance collect architecture-result --expected-bundle-id "$BUNDLE_ID" --count 8 --format json
```

Use the bundle identity returned by `design`, or omit `--expected-bundle-id`
when that identity is unavailable. The latter checks self-consistency only. The command defaults to interval
topology, exposes the full size–quality profile, and reports requested, available,
and delivered counts. It returns available members on shortfall. It does not
change the exact-count contract of ordinary `design` or `select_portfolio`.
A saved positive sequence-distance requirement is refused, not silently removed;
use the constrained selector for that request, or explicitly define a new
selection request through Python. `--out` only writes a new file.

An arrangement class describes the relative order, strands and overlap of the
selected strongest motif matches. [The grouping definition](reference/architecture-ranking.md#what-counts-as-an-architecture) explains which changes form a new class. Palindromic ties and equivalent reverse-complement inputs
use the same canonical replay. A small model perturbation can break a tie,
move a selected site and change class even when the balance stays unchanged;
this operation does not promise class stability near such ties.

## Try a small supplied pool

Run this example from any directory. The two synthetic motifs prefer AA and
CC. The supplied AACC and CCAA sequences satisfy both with different orders;
ACAC supplies a third selected architecture at lower quality.

```python
from motif_balance import DesignSpec, MotifModel, MotifSpecification
from motif_balance.alternatives import rank_architectures

left = MotifModel(
    motif_id="left",
    probabilities=((0.7, 0.1, 0.1, 0.1),) * 2,
    background=(0.25, 0.25, 0.25, 0.25),
)
right = MotifModel(
    motif_id="right",
    probabilities=((0.1, 0.7, 0.1, 0.1),) * 2,
    background=(0.25, 0.25, 0.25, 0.25),
)
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
sequences = ("AACC", "CCAA", "ACAC", "CACA", "AAAA", "CCCC")
ranking = rank_architectures(sequences, spec, grouping="interval_topology")
collection = ranking.select_up_to(8)
assert collection.requested_count == 8 and collection.delivered_count == 3
assert collection.status == "insufficient_retained_architectures"
for point in ranking.prefixes:
    print(
        f"{point.architecture_count} architecture(s): minimum balance {point.minimum_balance:.3f}"
    )
selected = ranking.select(2)
print("Selected:", ", ".join(item.sequence for item in selected))
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

## Continue from a saved design

Append this to the example above. First assess the same pair and length without
searching; then enumerate the small four-base space, save and inspect the result,
and select architectures from its retained sequences. The extra bases permit AA
and CC to sit separately. The structural score describes that lack of local
conflict; enumeration, not the descriptor, establishes the attainable score here.

```python
from pathlib import Path

from motif_balance import design
from motif_balance.artifacts import read_verified_portfolio
from motif_balance.assessment import assess_pair
from motif_balance.inspection import inspect_result
from motif_balance.inspection.render import render_text

assessment = assess_pair(left, right, length=spec.length, strands=spec.strands)
print(f"Pre-search structural score: {assessment.structural_score:.3f}")
search_spec = DesignSpec.model_validate({**spec.model_dump(mode="python"), "evaluations": 256})
portfolio = design(search_spec)
destination = Path("architecture-result")
portfolio.write(destination)
expected_id = portfolio.manifest.bundle_id
review = inspect_result(destination, kind="bundle", expected_bundle_id=expected_id)
print(render_text(review))

saved = read_verified_portfolio(destination, expected_bundle_id=expected_id)
pool = tuple(item.sequence for item in saved.manifest.elites)
recovered = rank_architectures(pool, saved.spec, grouping="interval_topology")
print("Recovered alternatives:", ", ".join(item.sequence for item in recovered.select(2)))
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

For your own bundle, begin at `read_verified_portfolio` with its explicit path
and a separately retained expected identity. That reader verifies the bytes and
replays published scores before returning both the saved inputs and retained
elites. Do not replace it with direct manifest parsing or reconstruct models
from a possibly changed configuration. Without an external expected identity,
verification establishes self-consistency, not independently trusted provenance.
The example uses the identity from the in-memory producer and creates a new
directory; it never overwrites an existing result. Choose a new destination
before rerunning it. [Inspection](reference/result-inspection.md) also provides
candidate SVGs when you need a visual explanation.

## Inspect a ranked alternative

Append this to the first supplied-pool example; the saved-design example is
not required. Inspect the second architecture, CCAA, with the same duplex,
filled windows and aligned information logos used for ordinary result review.
The first architecture is AACC: both score one, but their selected motif order
differs. The rank below comes from the explicit ranking, not from a run winner.

```python
from motif_balance import Candidate
from motif_balance.inspection import inspect_candidate
from motif_balance.inspection.render import render_candidate_svg
from motif_balance.model import candidate_id_for_sequence

representative = ranking.representatives[1]
candidate = Candidate(
    candidate_id=candidate_id_for_sequence(representative.evaluation.sequence),
    rank=representative.rank,
    **representative.evaluation.model_dump(mode="python"),
)
candidate_review = inspect_candidate(candidate, ranking.spec)
svg = render_candidate_svg(candidate_review)
review_json = candidate_review.model_dump_json(indent=2)
print(f"Inspected supplied rank {candidate.rank}: {candidate.sequence}")
```

`svg` is UTF-8 SVG bytes and `review_json` contains the numeric projection.
Inspection performs one additional score replay; rendering performs none.
Neither writes files, searches, reorders the collection, or verifies its source
history. The SVG explicitly labels this as a caller-supplied rank. Keep your
source and selection receipts separately; see the
[inspection contract](reference/result-inspection.md#inspect-a-supplied-candidate)
for validation and rendering limits.

## Calculation and reference

See [architecture grouping and ranking](reference/architecture-ranking.md) for definitions, formulas, returned fields,
resource limits and verification.
