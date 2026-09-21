---
doc_id: motif-balance-public-contract
title: Motif Balance public contract
intent: Define the supported scientific API, ordinary CLI, and artifact formats.
audience: [API consumers, integrators]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-20
doc_type: reference
journey: [integrate]

---

# Motif Balance public contract

## Python

For a runnable first task, start with the [Python tutorial](../python-api.md).
This page is the interface reference, not an installation walkthrough.

The main Python interface provides the input and result models, plus design
and scoring functions:

```python
from motif_balance import (
    MotifModel,
    MotifSpecification,
    DesignSpec,
    MotifMatch,
    Candidate,
    Portfolio,
    design,
    score,
)
```

`score(sequence, spec)` returns the authoritative immutable evaluation for one
supplied sequence without requiring a feasible output portfolio. The request's
count and portfolio-distance condition do not alter that sequence's score;
model, length, strand and scoring validation still apply. See
[sequence scoring](../score-sequences.md) for the input and failure boundaries.
`design(spec)` returns exactly `spec.count` ranked candidates or
raises a typed error. `Portfolio.write(path)` atomically publishes a new result
bundle. Inputs and public models are strict and immutable.

For directional requests, `design(spec, initialization="independent")` selects
eight independently initialized uniform DNA starts instead of the default
`"related"` starts. `design_observed` accepts the same keyword. This Python
method option does not change the scoring problem, moves, cooling schedule,
selection, or evaluator budget. It changes the recorded search-engine identity
and therefore the run identity. Unknown options and retired request schemas fail validation. Complete enumeration takes precedence for annealed
and greedy methods and does not use either initialization policy. The ordinary
CLI uses the default method.

`design(spec, method="greedy")` selects strict single-base improvement;
`design(spec, method="random")` selects independent whole-sequence draws with
replacement. Both require v3 and preserve scoring, selection, budget accounting,
and retention. Random draws have no chain initialization and never substitute
enumeration. `design_observed` accepts the same method option and replays the
recorded engine. See [method contracts](../methods.md#explicit-comparison-methods)
for ties, plateaus, partial trials, and exact-completion behavior.

Serialized numeric fields must be native YAML or JSON numbers; quoted numeric
strings are rejected. Advanced review uses an explicit submodule:

```python
from motif_balance.inspection import (
    CandidateInspection,
    ResultInspection,
    inspect_candidate,
    inspect_result,
)
```

`inspect_result` verifies an explicit bundle or execution workspace.
`inspect_candidate(candidate, spec)` replays one supplied directional candidate
without inventing a result or checking its caller-assigned rank. The latter
returns numeric support and uses the same candidate SVG renderer; it performs
no search or file access. It has no separate CLI command.
See [inspection](result-inspection.md#inspect-a-supplied-candidate) for its
input, replay, provenance and rendering boundaries.

Renderers, conversion helpers, bundle readers, and execution attestation remain
deliberate submodule or CLI surfaces. They are absent from the top-level
scientific facade and may evolve with their versioned artifact schemas.

The optional [claim-language check](claim-language.md) flags a bounded set of
wording hazards. It does not assess evidence or decide whether a claim is valid.

The explicit `motif_balance.assessment` module exports `assess_motifs`/`JointAssessment` for bounded two-to-four-model
exact joint arrangements, alongside `assess_pair` and
`PairAssessment`. The pair operation returns every relative arrangement; the joint operation
returns the best joint arrangement. Both calculate shared-base preference loss
without searching candidate sequences.
See [pair assessment](../pair-assessment.md) for the runnable example, independent
formula identity, output fields, equivalence rules, and typed refusal conditions.
It does not change `score`, `design`, or the top-level facade.

The explicit `motif_balance.alternatives.rank_architectures(sequences, spec)`
operation scores an explicit pool and returns an immutable
`architecture-ranking/v4` profile with explicit distance-budget accounting.
Its `select(count)` returns unchanged
evaluations for an exact quality-ranked architecture prefix or fails; it does
not search, publish a bundle, or enforce the portfolio's distance constraint.
See [choose alternatives](../choose-alternatives.md) for the executable example,
equivalence rules, separate distances, resource admission, and replay boundary.
The explicit `grouping` is `exact_offsets` (the preserved Python default) or
`interval_topology` (labeled endpoint order/equality and strand). The latter
groups spacing variants while preserving exact coordinates for inspection.
`select_up_to(count)` returns an `architecture-collection/v1` with explicit
partial delivery and weakest delivered quality. It does not turn partial
delivery into fulfillment of an exact-count request.
The same submodule's `measure_prefixes(ranking, order)` measures a complete
explicit representative order without editing or rescoring candidates. The
original order reuses its profile; another order incurs one bounded distance
pass. The corresponding `collect` CLI uses interval topology; advanced prefix
measurement remains a Python operation.

For a full set satisfying explicit separation and architecture requirements,
use `motif_balance.alternatives.select_portfolio(sequences, spec, policy)` and
`verify_portfolio_selection(result, sequences)`. The current
[portfolio contract](portfolio-selection.md) returns bottleneck quality and
finite-pool proof status without changing the original generation request.
It retains same-architecture variants until constrained selection. Neither
ranked prefixes nor supplied scores are accepted as an implicit substitute.
This operation is available through Python.

## Command line

The command line supports these tasks:

```text
assess   inspect a seek pair's length-dependent conflicts before search
design   validate or execute a DesignSpec
collect  select up to a requested number of architectures from retained elites
score    evaluate one supplied sequence
inspect  verify and review one immutable result
motif    prepare a motif model from an explicit source
animate  render recorded sequence states and best-score checkpoints
```

`assess LEFT RIGHT --length N` reads two explicit canonical YAML/JSON
`motif-model/v2` files. It emits a summary or the full `PairAssessment` JSON;
`--out` writes only a new file. Use `--additional` for a third or fourth desired motif; joint assessment
supports text and JSON. It does not accept a DesignSpec, search seed,
avoidance direction or multi-model database. The [assessment guide](../pair-assessment.md)
owns its runnable example, formula and interpretation.

`inspect` automatically verifies bytes, schemas, identities, and score replay.
It emits text by default and can export inspection JSON or one candidate,
portfolio, or search-record SVG. HTML is the optional linear composition of
those same renderers.

Motif preparation is available in ordinary help. Exact-wheel execution is an
advanced integration command:

```text
motif-balance orchestration execute ...
```

Motif preparation converts one explicitly supplied supported source. It does
not discover or fetch databases. Orchestration binds an execution to an exact
wheel and producer revision. Both operate on explicitly supplied files.

[Playback](playback.md) replays an explicit search observation and exports HTML,
SVG or optional media. It reports recorded states without interpolating missing
search events.

## Artifacts

A result bundle contains:

```text
design.json
motifs.json
candidates.tsv
matches.tsv
manifest.json
candidates.fasta  # derived, manifest-bound
```

The manifest binds every other member by relative path, size, and SHA-256.
Verification recompiles the problem and replays each published candidate's
matches, directional satisfaction, and
hard-minimum score. Directional manifests also replay every retained elite and
bind exact-completion counts or an explicit bounded-run status. Current
manifests bind the complete best observed evaluation even when it is excluded
from the distance-constrained selected portfolio. Verification does not rerun
search. Text, inspection JSON, SVG, and HTML are regenerable projections outside
the bundle.

The reader and writer use only `run-manifest/v7` for directional v3 inputs. New
bundle projections use `motif-balance.result-inspection/v5`; supplied-candidate
projections use `motif-balance.candidate-inspection/v2`. Unknown schemas fail
closed. Retired scoring and artifact formats are not converted; historical
records require their original software. A workflow that
needs exact runtime identity retains the complete
`motif-balance.execution-workspace/v1` with its wheel and external trust
anchors.

Verification checks the saved computational result. Biological interpretation
and comparisons across runs require the corresponding experimental evidence.

Directional runs may request [bounded search observations](search-observations.md)
from the same search as the returned portfolio. No complete-pool compatibility
module is shipped; historical observations require their original producing build.
These retain separate chain snapshots, exact first-hit counts, and move-change
counts without changing the canonical portfolio. They are not a complete pool
or a replacement for the manifest's elite reservoir.
