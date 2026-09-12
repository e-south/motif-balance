---
doc_id: motif-balance-search-observations
title: Observing search recovery
intent: Explain bounded, passive search diagnostics and their replay contract.
audience:
  - integrators
  - maintainers
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-07
doc_type: reference
---

# Observing search recovery

Use observations when an experiment needs to distinguish best-so-far recovery
from the states currently explored by each search chain. The optimizer,
evaluation budget, RNG stream, selected portfolio, and canonical bundle remain
unchanged. Pair choice, comparisons, figures, and retention policy belong to the
caller; the product implements the declared bounded retention mechanically.

## Explicit Python operation

Given a validated directional `DesignSpec` named `spec`:

```python
from motif_balance.api import design_observed, read_search_observation
from motif_balance.model.search_observation import ObservationSpec

portfolio, observation = design_observed(
    spec,
    ObservationSpec(
        max_snapshots=32,
        score_targets=(0.5, 0.8, 0.95),
        quality_thresholds=(0.5, 0.8, 0.95),
        max_sequences_per_threshold=64,
    ),
)
encoded = observation.model_dump_json().encode("utf-8")
replayed = read_search_observation(encoded)
assert replayed == observation
```

Targets above are illustrative model-score thresholds, not biological cutoffs.
The advanced helpers are explicit submodule imports, not top-level scientific
verbs. V1/v2 designs are refused; no legacy observation fallback is attempted.

To compare initialization methods, supply `initialization="independent"` to
both `design` and `design_observed`. Observation remains passive within each
method; changing initialization changes the experiment, not the observation
policy. Independent starts draw every base uniformly from A/C/G/T for each
chain, without requiring distinct sequences or a minimum distance. The default
`"related"` policy retains one origin with small perturbations. Both use eight
starts, or the available evaluator budget if smaller.

`method="greedy"` uses the same starting sequences and records
`greedy_multistart_v1` or `greedy_independent_starts_v1`.
`method="random"` records `uniform_random_v1` and has no chain initialization.
All methods use the same passive quality retention and exact target-hit
accounting. Replay selects the recorded engine and rejects unknown identities
or a relabeled trajectory. There is no automatic method selection.
Annealed and greedy calls enumerate when the budget covers the complete space;
those calls record `exhaustive_v1`. Random calls always draw with replacement.
See [methods](../methods.md#explicit-comparison-methods) for the complete policy.

## What is recorded

- Each snapshot has its actual evaluation count, the incumbent evaluation, and
  each current chain's identity and evaluation. Snapshots follow completed
  proposals; four-base resampling can cross the nominal sampling interval.
- Initialization is one snapshot after the starts are evaluated. Complete
  enumeration and uniform random sampling have no search chains and record an
  empty state tuple. Random snapshots record the incumbent, not fictitious moves.
- Target hits are the exact first evaluator-call indices, observed during
  scoring. An unreached target has a null hit, not a zero or a fabricated time.
- Move counts distinguish attempted, accepted, sequence-changing, improving,
  and decreasing transitions. Improvements refer to the public hard minimum.

The incumbent includes every scored proposal, even one not adopted as a chain
state. Its score cannot decrease. Individual motif scores can decrease while
their minimum improves. Never connect alternating chains into one trajectory.
Temperature controls exploration, not the definition of the objective landscape.

## Alternatives at declared quality

`quality_thresholds` is optional and contains at most 16 unique increasing
scores in [0, 1]. Each threshold means balance **at least** that value; these
sets overlap, rather than partitioning scores into disjoint bins. The caller
declares 1–256 retained sequences per threshold (default 64).

For each threshold, retention keeps the exact distinct evaluated sequences
with the lowest SHA-256 sequence hashes, using the sequence as the collision
tie-breaker. This is a deterministic hash-priority sample, not elite ranking.
Repeated evaluator calls count toward `qualifying_evaluations`, but not
`unique_sequences` or additional retained alternatives. Every retained row is
the original authoritative evaluation. No additional score calls, RNG draws,
unbounded observer seen-set, or search decisions are introduced.

`quality_samples` records the threshold, qualifying calls, encountered unique
sequence count, and retained evaluations, including an explicit empty tuple
when nothing qualified. The ordinary elite archive remains unchanged. Complete
coverage means all qualifying **encountered** sequences were retained, never
all possible sequences unless the search itself was exhaustive.

Reverse-complement equivalence, fixed-size comparisons, placement diversity,
and near-best analysis remain caller-owned. Exact sequences are the retention
unit even under both-strands scoring. Hash retention does not turn a biased
optimizer encounter set into uniform sequence-space samples.

## Limits and verification

The caller declares 2–256 snapshots and at most 32 unique increasing targets.
Admission bounds projected snapshot and sample bases, repeated identifiers,
match metadata, and serialized bytes before search. Unchecked model copies are
revalidated. An independent 64 MiB serialized-byte check precedes return.
Observation records are strict, immutable `search-observation/v2` objects.
`read_search_observation(bytes)` refuses payloads above 64 MiB before parsing
and reruns the deterministic search to verify snapshots, counts, identities,
first hits, and quality-sample membership. Verification costs another search; measure it
separately from optimization. An unknown schema or replay mismatch fails.

The preliminary development-only v1 observation omitted quality samples and
is not accepted by this reader. Preserve its original source-bound diagnostic
receipt when retaining old observations; do not relabel old bytes as v2.
No canonical portfolio or published run-manifest schema changes here.

The caller owns byte storage and must bound file reads before supplying bytes.
Observations are not inserted into canonical bundles, and are not full proposal
histories, uniform sequence-space samples, or proof of convergence. Sparse
snapshot curves must not be presented as exact trajectories between samples.

For ordinary result interpretation, return to [methods](../methods.md) and
[the public contract](public-contract.md).
