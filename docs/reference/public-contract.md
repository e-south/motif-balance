---
doc_id: motif-balance-public-contract
title: Motif Balance public contract
intent: Define the supported scientific API, ordinary CLI, and artifact seam.
audience:
  - API consumers
  - integrators
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-08
doc_type: reference
journey:
  - integrate
---

# Motif Balance public contract

## Python

For a runnable first task, start with the [Python tutorial](../python-api.md).
This page is the interface reference, not an installation walkthrough.

The top-level facade has six nouns and two verbs:

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
and therefore the run identity. Unknown options fail; v1/v2 requests refuse
independent initialization. Complete enumeration takes precedence for annealed
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
no search or file access. It is unreleased and has no separate CLI command.
See [inspection](result-inspection.md#inspect-a-supplied-candidate) for its
input, replay, provenance and rendering boundaries.

Renderers, conversion helpers, bundle readers, and execution attestation remain
deliberate submodule or CLI surfaces. They are absent from the top-level
scientific facade and may evolve with their versioned artifact schemas.

The optional [claim-language check](claim-language.md) flags a bounded set of
wording hazards. It does not assess evidence or decide whether a claim is valid.

The explicit `motif_balance.assessment` seam exports `assess_pair` and
`PairAssessment`. It calculates a bounded, length-aware seek-pair conflict
profile from two current motif models, without sequence search or publication.
See [pair assessment](../pair-assessment.md) for the runnable example, independent
formula identity, output fields, equivalence rules, and typed refusal conditions.
It does not change `score`, `design`, or the top-level facade.

The explicit `motif_balance.alternatives.rank_architectures(sequences, spec)`
operation scores an explicit pool and returns an immutable
`architecture-ranking/v2` profile with explicit distance-budget accounting.
Its `select(count)` returns unchanged
evaluations for an exact quality-ranked architecture prefix or fails; it does
not search, publish a bundle, or enforce the portfolio's distance constraint.
See [choose alternatives](../choose-alternatives.md) for the executable example,
equivalence rules, separate distances, resource admission, and replay boundary.
The same submodule's `measure_prefixes(ranking, order)` measures a complete
explicit representative order without editing or rescoring candidates. The
original order reuses its profile; another order incurs one bounded distance
pass. These unreleased operations add no top-level facade verb or CLI command.

## Command line

The ordinary command help exposes four journeys:

```text
assess   inspect a seek pair's length-dependent conflicts before search
design   validate or execute a DesignSpec
score    evaluate one supplied sequence
inspect  verify and review one immutable result
```

`assess LEFT RIGHT --length N` reads two explicit canonical YAML/JSON
`motif-model/v2` files. It emits a summary or the full `PairAssessment` JSON;
`--out` writes only a new file. It does not accept a DesignSpec, search seed,
avoidance direction, or multi-model database. The [assessment guide](../pair-assessment.md)
owns its unreleased status, runnable example, formula, and interpretation.

`inspect` automatically verifies bytes, schemas, identities, and score replay.
It emits text by default and can export inspection JSON or one candidate,
portfolio, or search-record SVG. HTML is the optional linear composition of
those same renderers.

Advanced integration commands are intentionally hidden from ordinary help:

```text
motif-balance motif prepare ...
motif-balance orchestration execute ...
```

Motif preparation converts one explicitly supplied supported source. It does
not discover or fetch databases. Orchestration binds an execution to an exact
wheel and producer revision. Neither operation adds a new scientific verb.

## Artifacts

The immutable result seam is:

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
matches, directional satisfaction, constraint state where applicable, and
hard-minimum score. Directional manifests also replay every retained elite and
bind exact-completion counts or an explicit bounded-run status. Current
manifests bind the complete best observed evaluation even when it is excluded
from the distance-constrained selected portfolio. Verification does not rerun
search. Text, inspection JSON, SVG, and HTML are regenerable projections outside
the bundle.

Version `0.5` reads `run-manifest/v2` through `run-manifest/v6`. A v3
directional input writes v6; an explicit legacy v2 input still writes v5. New
bundle projections use `motif-balance.result-inspection/v4`; supplied-candidate
projections use `motif-balance.candidate-inspection/v1`. Unknown schemas fail
closed. V1 remains readable and scoreable but cannot initiate a new design
publication. A workflow that
needs exact runtime identity retains the complete
`motif-balance.execution-workspace/v1` with its wheel and external trust
anchors.

Package verification establishes product integrity. It does not accept a
scientific claim, define a benchmark cohort, or confer manuscript status.

Legacy v2 downstream analyses that require the complete unique evaluated pool may use
the deliberately advanced `motif_balance.observation` submodule. Its single
bounded JSON record is immutable, canonical, path-free, identity-checked, and
scientifically replayed. The observer admits at most 32,768 evaluator calls
and independently limits the encoded record to 64 MiB. Directional v3 runs
refuse this complete-pool export and instead retain a deterministic score-ranked
reservoir of at most 256 unique evaluations in the manifest. It is not a
`Portfolio`, canonical bundle member, CLI journey, or top-level export.

An analysis that needs both outputs from one declared evaluator budget may use
`motif_balance.observation.design_with_evaluated_pool(spec)`. It returns the
ordinary immutable `Portfolio` and complete observation derived from the same
search result. It adds no top-level symbol or CLI command.

Directional runs may instead request [bounded search observations](search-observations.md).
These retain separate chain snapshots, exact first-hit counts, and move-change
counts without changing the canonical portfolio. They are not a complete pool
or a replacement for the manifest's elite reservoir.
