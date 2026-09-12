---
doc_id: motif-balance-choose-alternatives
title: Choose alternative motif architectures
intent: Rank supplied sequences by distinct selected-match architecture and inspect every supported collection size.
audience:
  - users
  - API consumers
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-11
doc_type: how-to
journey:
  - integrate
---

# Choose alternative motif architectures

Finding one good sequence does not tell you whether other useful arrangements
remain. `rank_architectures` scores a supplied sequence pool, keeps its best
representative of each selected-match architecture, and ranks those
representatives by quality. Choose the collection size you need and inspect
the weakest score retained. There is no mandatory 32-design endpoint or quality
cutoff, and this operation performs no search.

This explicit Python API is unreleased. Use the current source installation
from the [quickstart](quickstart.md#install), or a verified build containing
the operation. It has no CLI command and does not change ordinary `design`
portfolio selection.

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
ranking = rank_architectures(sequences, spec)
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
four architectures fails: these supplied sequences support only three under
the declared selected-match policy. That does not prove a fourth is impossible.

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
recovered = rank_architectures(pool, saved.spec)
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

## Reuse the scoring context explicitly

Reuse the `DesignSpec` that defines your sequences' scoring context. The verified
bundle above or a caller-owned sequence list can supply the pool; the operation
does not discover files or merge runs.
Only models, directions, length, and strands determine the scores. The
request's seed, evaluator budget, and target count remain recorded context,
not ranking limits or search activity. `select(count)` controls the returned
count. Even an original count that exceeds the complete sequence space does not
prevent ranking a valid supplied pool; trying to generate that impossible
portfolio with `design` still fails. The specification must still satisfy its
schema and resource limits, and every motif must fit the sequence length.
A positive `min_distance` is refused rather than silently ignored;
use ordinary [portfolio selection](../IA.md#selection) for that contract.
In particular, the first-design Python tutorial requests positive sequence
distance. Its saved request is therefore not an architecture-ranking request.
Changing that selection requirement must be an explicit caller decision, not
an automatic conversion or a claim that architecture selection enforces it.

## What counts as an architecture?

Each canonical sequence is authoritatively scored once. The strongest match
of every specification has one deterministically selected position and strand.
The relative positions, motif order, and same/opposite strand relationships
form the architecture. Moving the entire arrangement together does not add a
class. When both strands are allowed, a global reverse complement does not
add a sequence or architecture class either.

Reverse-complement canonicalization occurs **before scoring**. The returned
sequence can therefore be the reverse complement of a supplied literal.
No sequence changes after evaluation. Replaying the canonical literal also
makes tied selected sites independent of which orientation was supplied.
Other equally strong placements are not enumerated. For an avoid specification,
the selected site is its strongest unwanted match, not a desired installed site.

Each class contributes its highest-balance sequence, breaking score ties by
canonical sequence. Equal-quality representatives still have a deterministic
order. `quality_steps` includes every tied architecture at each distinct score
boundary; `prefixes` instead includes every supported integer collection size.

## Read quality and differences separately

| Field on each prefix | Meaning |
| --- | --- |
| `architecture_count` | Number of distinct selected-match architectures included. |
| `minimum_balance` | Weakest representative score in that collection. |
| `mean_sequence_distance` | Mean fraction of differing bases across representative pairs. |
| `mean_selected_footprint_distance` | Mean differing-base fraction within the union of each pair's selected motif footprints. |
| `mean_spacing_distance_nt` | Mean absolute change in motif-pair center separations, in nucleotides. |
| `mean_orientation_difference` | Fraction of motif-pair same/opposite strand relationships that differ, averaged across representatives. |

Pairwise distances are undefined (`None`) for one representative. Sequence
and footprint comparisons use one common orientation, chosen by least
whole-sequence difference, then footprint difference on a tie. Geometry
distances average over all labeled motif pairs, so renaming motifs does not
change them. Two motif orders can be distinct architectures with identical
spacing and relative orientation. Inspect the returned matches as well.

Minimum quality cannot rise as you include more ranked architectures. At a
fixed rank it cannot fall if the supplied pool genuinely expands under the
same scoring and equivalence policy. The distance averages have neither
guarantee. This is quality-first distinct-class selection, not maximum
dispersion or a measurement of all sequence alternatives within each class.

If a caller needs to preserve a different order of the same representatives,
use `motif_balance.alternatives.measure_prefixes(ranking, order)`, where `order`
is a tuple or list of their sequence strings. It requires a complete permutation;
it cannot add, omit, edit or rescore a representative. Each returned prefix
reports its weakest score and separate distances in that explicit order.
This is measurement, not a new quality or diversity-ranking policy. An unchanged
order reuses the existing prefixes; another order performs one additional
distance pass under the same independent caps. Retain the supplied order beside
the result when reproducing a caller-owned collection.

## Contract and failure boundaries

The API is `rank_architectures(sequences, spec, *, distance_base_budget=10_000_000)`.
`sequences` must be a tuple
or list of uppercase, fixed-length A/C/G/T strings; `spec` must be a current
directional request with at least two specifications. Iterators, legacy
requests, mixed lengths, and unsupported distance constraints are refused.
The pool limit is 50,000 records and 10 million supplied bases. Scoring is
admitted against 100 million base operations. All-prefix distance work defaults
to ten million conservative base/pair terms. After profiling the intended pool,
an explicit integer `distance_base_budget` may admit up to 500 million terms.
That budget cannot override the independent caps of 500,000 representative
pairs and 250,000 prepared motif-pair entries. Oversized requests raise
`ValueError` before distance preparation; no pool is silently truncated.

For `n` representatives, `m` specifications and length `L`, the term estimate is
`n*(n-1)/2 * (L*s + m*(m-1))`, where `s` is 4 for both strands and 2 for forward
only. Preparation needs `n*m*(m-1)/2` entries when `n >= 2`; a singleton prepares
none. The independent caps bound quadratic pair work and temporary preparation
separately. A larger requested budget changes admission, not the distance values.

Distance work is exact, not sampled. After admission, the implementation prepares
each representative's bases, selected footprints and motif-pair separations once,
then reuses them across comparisons. This temporary, request-local representation
avoids repeated per-base scans; it does not change scores, orientation choices,
or the input pool. Work estimates are not counts of Python instructions or
runtime promises. The limits apply even when this exact calculation is fast
on a particular machine; there is no unlimited mode or automatic retry with
a larger budget.

The immutable `architecture-ranking/v2` record includes the full specification,
a digest of the sorted supplied sequence multiset, input-record/literal/class
counts, scoring calls, requested distance budget, computed distance-term count,
representatives, and prefixes. Its validator checks that the recorded distance
work agrees with the representatives and satisfies all three caps. Earlier
unreleased v1 records are not relabeled or silently upgraded: preserve them with
their original tool build, or rerun from trusted sequences and specification.
Duplicate literals count
as input records but are scored only once; allowed reverse complements share
a scoring call. `search_evaluations` is always zero. Empty pools retain empty
profiles and cannot satisfy a positive selection request.

Coverage is always `supplied_pool`. A capped search archive can omit useful
architectures, and adding a longer run does not guarantee a nested pool.
Neither the digest nor JSON schema validation independently proves that a
serialized profile represents the original complete pool. Re-run this API
on the retained sequences and trusted specification to reproduce it; a ranking
record is not a verified search bundle or a scientific acceptance receipt.
See [pair assessment](pair-assessment.md) to inspect motif conflicts before
search, and [interpretation limits](limitations.md) before making broader claims.
