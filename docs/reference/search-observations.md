---
doc_id: motif-balance-search-observations
title: Observing search recovery
intent: Explain bounded, passive search diagnostics and their replay contract.
audience: [integrators, maintainers]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-21
doc_type: reference
---

# Observing search recovery

Use observations when an experiment needs to distinguish best-so-far recovery
from the states currently explored by each search chain. The optimizer,
evaluation budget, RNG stream, selected portfolio, and canonical bundle remain
unchanged. Specify the checkpoints and quality thresholds needed for the comparison.
Request exact incumbent receipts when an illustration needs to show the actual
best sequence at a particular amount of search effort.

Use [playback](playback.md) to display the recorded sequences and scores.

## Explicit Python operation

This complete synthetic example records a search without creating files:

```python
# Import the models and operations used in this example.
from motif_balance import DesignSpec, MotifModel, MotifSpecification
from motif_balance.api import design_observed, read_search_observation
from motif_balance.model.search_observation import ObservationSpec

# Define two motifs and a seven-base search with a fixed evaluation budget.
spec = DesignSpec(
    schema_version="design-spec/v3",
    specifications=tuple(
        MotifSpecification(
            direction="seek",
            motif=MotifModel(
                motif_id=f"synthetic_{word}",
                background=(0.25,) * 4,
                probabilities=tuple(
                    tuple(0.7 if base == preferred else 0.1 for base in "ACGT")
                    for preferred in word
                ),
            ),
        )
        for word in ("AC", "CG")
    ),
    length=7,
    evaluations=127,
    count=1,
    strands="both",
    seed=19,
)
# Run the search while recording chosen score levels and evaluation counts.
portfolio, observation = design_observed(
    spec,
    ObservationSpec(
        max_snapshots=32,
        score_targets=(0.5, 0.8, 0.95),
        incumbent_evaluations=(1, spec.evaluations),
        quality_thresholds=(0.5, 0.8, 0.95),
        max_sequences_per_threshold=64,
    ),
)
# Serialize the observations to portable JSON bytes.
encoded = observation.model_dump_json().encode("utf-8")
# Reload and verify the recorded sequences and scores.
replayed = read_search_observation(encoded)
# Check that replay preserves the observation exactly.
assert replayed == observation
# Collect the exact evaluation counts requested for best-sequence snapshots.
calls = ", ".join(str(row.evaluations) for row in observation.incumbents)
# Print the search budget used and the recorded snapshot counts.
print(f"{observation.evaluation_count} evaluations; exact incumbent calls: {calls}")
```

Targets above are illustrative model-score thresholds, not biological cutoffs.
The example uses a budget greater than one. Exact incumbent counts must
be distinct, increasing, and no greater than the requested search budget.
Import the observation helpers from `motif_balance.api`. Only current directional design requests are accepted.

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
- `incumbents` contains one receipt per declared `incumbent_evaluations` count.
  Each holds the literal best evaluation at that call, including its sequence,
  selected sites, and per-motif scores. It can fall inside a multi-score proposal
  and is not a chain-state snapshot. If enumeration finishes before the requested
  call, its incumbent is null; the final sequence is not relabeled as a later result.
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
declares 1–1,024 retained sequences per threshold (default 64), subject to the
combined size limits below.

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

For a small retention check, a threshold of zero and a capacity at least as
large as the evaluator budget retain every distinct encounter, if admitted.
Compare selection from this bounded reference with selection from a smaller
retained pool under the same search request and selector policy. The larger
capacity is explicit and opt-in; it does not change the default retention or
establish that a smaller sample is sufficient for other requests.

To select a differentiated collection, combine `portfolio.manifest.elites`
with the desired `quality_samples` evaluations, deduplicate literal sequences,
then supply those sequences to [portfolio selection](portfolio-selection.md).
Keep generation `count=1` when measuring one search winner against a selected
collection. Selection's `PortfolioPolicy.count` sets the collection size; it
does not change the preceding search. Rescoring and selection cost are separate
from the generation budget. A full collection's weakest score cannot exceed
that same search's best observed score.

Define reverse-complement equivalence, collection size and placement comparison
rules when analyzing the retained sequences. Exact sequences are the retention
unit even under both-strands scoring. Hash retention does not turn a biased
optimizer encounter set into uniform sequence-space samples.

## Limits and verification

The caller declares 2–256 snapshots, at most 32 score targets, and at most 32
exact incumbent counts. Admission bounds projected snapshot, incumbent, and sample bases, repeated identifiers,
match metadata, and serialized bytes before search. Unchecked model copies are
revalidated. An independent 64 MiB serialized-byte check precedes return.
Observation records are strict, immutable `search-observation/v4` objects.
`read_search_observation(bytes)` refuses payloads above 64 MiB before parsing
and reruns the deterministic search to verify snapshots, counts, identities,
first hits, exact incumbents, and quality-sample membership. Verification costs another search; measure it
separately from optimization. An unknown schema or replay mismatch fails.

Only the current observation schema is accepted. Retained historical observations
remain tied to their producing software; do not relabel their bytes or adapt them
implicitly during replay.
No canonical portfolio or published run-manifest schema changes here.

The caller owns byte storage and must bound file reads before supplying bytes.
Observations are not inserted into canonical bundles, and are not full proposal
histories, uniform sequence-space samples, or proof of convergence. Sparse
snapshot curves must not be presented as exact trajectories between samples.

For ordinary result interpretation, return to [methods](../methods.md) and
[the public contract](public-contract.md).
