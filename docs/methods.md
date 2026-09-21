---
doc_id: motif-balance-methods
title: Scoring and search methods
intent: Define the calculations behind sequence scores and bounded search.
audience: [users]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-20
doc_type: reference
---

# Scoring and search methods

The design problem is to improve the weakest motif requirement within a fixed
DNA length. Scoring defines that objective. Search chooses which sequences to
evaluate, and selection chooses the returned candidates. All methods below use
the same scoring calculation.

## Scoring a candidate

A motif input contains a probability for each base at each position and an
explicit background distribution. For position *j* and nucleotide *b*, convert
the supplied probability to a log-likelihood-ratio weight:

```text
weight[j, b] = log2(probability[j, b] / background[b])
```

For a motif of width *w*, sum these weights over each matching-length sequence
window. Scan every valid offset and each allowed strand, then keep the highest
sum, `best_llr`. Raw scores within `1e-12` are ties; choose the leftmost start,
then the plus strand. Reverse-strand matches are evaluated in their own 5′→3′
orientation and recorded in the original sequence's coordinates.

To express each motif's match on its own available score range, sum the minimum
weight in each motif column to obtain `minimum_llr`; sum the column maxima to
obtain `maximum_llr`. Scale the selected match by:

```text
attainment = (best_llr − minimum_llr) / (maximum_llr − minimum_llr)
```

These endpoints describe individual motif-width sequences. A longer sequence's
best scanned match can reach one by containing a maximizing site, while it may
not be possible to make every window score at the minimum. A zero score range
is rejected because the ratio would be undefined. This calculation is
`relative_pwm_attainment_v2`; it does not add pseudocounts during search.
[Motif preparation](motif-models.md) describes the input conversions.

Each motif contributes one directional satisfaction: attainment for `seek`, or
one minus attainment for `avoid`. The minimum satisfaction across requirements
is the reported `balance_score`. This hard minimum is the score used to rank
candidates.

## Default search

When `4^length` fits within the requested evaluation budget, the default policy
visits every sequence and records `exhaustive_v1`. Otherwise it runs a bounded
multi-start annealed local search. An evaluation means scoring one complete
candidate against every requirement; initialization and repeated candidates
also consume this budget.

The default `related` initialization uses eight internal states, or fewer when
the budget is below eight. It begins with one uniform random sequence and
perturbs seven copies at `max(1, round(0.02 × length))` distinct positions.
These states are part of one seeded run. To use independent uniform starts,
pass `initialization="independent"` from Python. The recorded engine distinguishes
`annealed_multistart_v1` from `annealed_independent_starts_v1`.

Search mixes single-coordinate resampling, contiguous-block replacement,
dispersed replacements and motif-guided interval overwrites. Every proposal
preserves length and is rescanned. Proposals can focus near the currently
limiting match. A smooth approximation to the minimum guides exploration;
a separate inverse-temperature schedule progressively reduces acceptance of
worsening moves. Neither quantity replaces the public balance score.
The versioned move and acceptance rules are implemented in
[search policy](../src/motif_balance/search/policy.py) and
[proposal generation](../src/motif_balance/search/moves.py).

The best evaluated sequence is recorded separately from each state's current
sequence. An evaluated proposal can improve that record even if the search
does not adopt it as a current state. Checkpoint curves therefore show best
recovery, not the complete history of accepted moves.

## Explicit comparison methods

Python `design(spec, method=...)` and `design_observed` accept `"annealed"`,
`"greedy"` or `"random"`. They share scoring, evaluation accounting, retention
and selection. The CLI uses the default method.

Greedy search uses the same related or independent starts as annealed search.
It visits states in turn, chooses a random coordinate, and scores A, C, G and T
at that coordinate, including the unchanged base. It adopts only a strict
improvement in balance; improving ties use lexical sequence order. It does not
cross neutral plateaus or restart after stagnation. A final partial trial uses
only the remaining evaluations. Engines are `greedy_multistart_v1` and
`greedy_independent_starts_v1`.

Random search draws one whole sequence per evaluation, choosing each base
uniformly with NumPy PCG64. Sampling allows repeats. It has no search states,
so omit `initialization`. Its engine is `uniform_random_v1` and it always
samples, even when the budget could enumerate the space.

Annealed and greedy requests both enumerate when the full space fits. Inspect
the recorded engine when comparing methods, since an exhaustive run did not
execute either heuristic. Equal evaluation counts match the number of complete
candidate scores, not elapsed time: score cost also depends on length, motif
widths, motif count and strand policy.

## Budget, retention, and interpretation

Search retains all unique evaluations in memory for exact discovery accounting
and selection. The manifest exports at most 256 distinct high-scoring sequences,
plus logarithmic score checkpoints, final state scores and proposal counts.
The export cap is not a working-memory bound. Optional
[observations](reference/search-observations.md) retain explicit snapshots,
evaluated winners and bounded samples above chosen quality thresholds.

Selection orders immutable evaluations by descending balance and lexical
sequence order. With a distance requirement, it searches for an exact-size set
meeting that constraint. It never relaxes the requested count or distance.
A bounded selection limit is reported separately from demonstrated infeasibility.
See [design inputs](design-spec.md) and [portfolio selection](reference/portfolio-selection.md).

The result bundle preserves the request, motif contents, candidates, matches
and manifest. Publication refuses existing destinations and verification replays
scores. A bounded run establishes what was recovered with that effort; a
complete enumeration establishes the optimum for those inputs. Comparisons
across models or conditions require explicit controls and repeated runs.
