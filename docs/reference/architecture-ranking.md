---
doc_id: motif-balance-architecture-ranking
title: Architecture grouping and ranking
intent: Define the calculation, returned records and validation limits.
audience: [API consumers]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-20
doc_type: reference
---

# Architecture grouping and ranking

## Reuse the scoring context explicitly

Reuse the `DesignSpec` that defines your sequences' scoring context. Use retained sequences from a verified bundle or an explicit sequence list.
The [selection guide](../choose-alternatives.md) demonstrates both.
Only models, directions, length, and strands determine the scores. The
request's seed, evaluator budget, and target count remain recorded context,
not ranking limits or search activity. `select(count)` controls the returned
count. Even an original count that exceeds the complete sequence space does not
prevent ranking a valid supplied pool; trying to generate that impossible
portfolio with `design` still fails. The specification must still satisfy its
schema and resource limits, and every motif must fit the sequence length.
A positive `min_distance` is refused rather than silently ignored;
use [constrained portfolio selection](portfolio-selection.md) for that contract.
In particular, the first-design Python tutorial requests positive sequence
distance. Its saved request is therefore not an architecture-ranking request.
Changing that selection requirement must be an explicit caller decision, not
an automatic conversion or a claim that architecture selection enforces it.

## What counts as an architecture?

Each canonical sequence is scored once with the shared evaluator. The strongest match
of every specification has one deterministically selected position and strand.
Two explicit groupings use those same selected matches:

- `interval_topology` replaces all distinct start/end coordinates by their sorted
  ranks, retaining equal endpoints and each labeled motif's strand. This captures
  order, gap versus touching, crossing overlap, containment and coincidence for
  every motif pair, including sets larger than two. A change of gap size or
  overlap depth within the same relationship stays in one class. Crossing an
  endpoint boundary, even by one base, changes the declared relationship. The
  policy makes no minimum biological effect-size claim.
- `exact_offsets` preserves exact relative center offsets and same/opposite
  strand relationships. It can count single-base spacing changes separately.

Moving the entire arrangement together does not add a class. When both strands
are allowed, a whole-duplex reversal does not add a sequence or architecture
class. Forward-only requests keep reverse-complement sequences distinct. Model identities are
never interchangeable. Class identity and literal sequence identity are separate;
the result retains both `architecture_class` and exact `geometry`.

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

The API is `rank_architectures(sequences, spec, *, grouping="exact_offsets", distance_base_budget=10_000_000)`.
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

The immutable `architecture-ranking/v4` record includes the full specification,
a digest of the sorted supplied sequence multiset, input-record/literal/class
counts, scoring calls, requested distance budget, computed distance-term count,
grouping, representatives, and prefixes. Its validator checks that class keys
agree with actual selected matches and that the recorded distance
work agrees with the representatives and satisfies all three caps. Earlier
unreleased records are not relabeled or silently upgraded: preserve them with
their original tool build, or rerun from trusted sequences and specification.
Duplicate literals count
as input records but are scored only once; allowed reverse complements share
a scoring call. `search_evaluations` is always zero. Empty pools retain empty
profiles and cannot satisfy a positive selection request.

`select_up_to(count)` returns an immutable `architecture-collection/v1` with the
ranking digest, grouping, requested/available/delivered counts, members, weakest
delivered quality, and `complete` or `insufficient_retained_architectures` status.
It performs no additional scoring or selection search. No sequence-distance
threshold is imposed by either grouping. Positive separation requirements still
belong to the unpruned constrained selector; pruning class winners first would
discard potentially necessary feasible combinations.

Coverage is always `supplied_pool`. A capped search archive can omit useful
architectures, and adding a longer run does not guarantee a nested pool.
Neither the digest nor JSON schema validation independently proves that a
serialized profile represents the original complete pool. Re-run this API
on the retained sequences and trusted specification to reproduce it; a ranking
record is not a verified search bundle or evidence of the original pool's completeness.
See [pair assessment](../pair-assessment.md) to inspect motif conflicts before
search, and [interpretation limits](../limitations.md) before making broader claims.
