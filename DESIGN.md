---
doc_id: motif-balance-design-contracts
title: Motif Balance engineering contracts
intent: State public semantics, invariants, and change rules.
audience:
  - maintainers
  - API consumers
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-07
doc_type: explanation
---

# Motif Balance engineering contracts

## Public contracts

The public scientific vocabulary is `MotifModel`, `MotifSpecification`,
`DesignSpec`, `MotifMatch`, `Candidate`, `Portfolio`,
`design(spec) -> Portfolio`, and `score(...)`.
`Evaluation`, `ResultInspection`, and `CandidateInspection` are internal or operational typed records,
not additional top-level scientific nouns.
Scientific inputs belong in an immutable `DesignSpec`; operational CLI options
may select output or validation behavior but cannot revise that specification.

The explicit `motif_balance.assessment.assess_pair` seam instead takes two
current motif models, length, and strands. Its versioned `PairAssessment` is a
pre-search local-conflict profile, not an `Evaluation`, `Portfolio`, or calibrated
outcome prediction. It does not require or manufacture search-budget/count fields.
The [assessment contract](docs/pair-assessment.md) owns its formula, translation/
reverse-complement equivalence, complete relative-arrangement coverage, and
zero-range-column policy. Existing scoring, search, and artifact schemas are
unchanged; callers must not relabel another formula as this assessment version.

The explicit `motif_balance.alternatives.rank_architectures` seam scores a
supplied sequence pool under a current `DesignSpec` and returns every
quality-ranked selected-architecture prefix. Canonicalization precedes scoring;
selection returns unchanged evaluations and never silently relaxes count or
distance requirements. Coverage remains supplied-pool, not search-space coverage.
The [selection guide](docs/choose-alternatives.md) owns equivalence, ranking,
distance, resource, and serialization boundaries. No search or bundle schema changes.
The unreleased `architecture-ranking/v2` record adds explicit distance-budget
accounting. It uses the same measurements, with independent representative-pair
and prepared-motif-pair caps. Old v1 records remain tied to their original build;
there is no in-place migration or permissive reader. Empty and singleton rankings
perform no pair-distance preparation.

## Invariants

- Public models are strict, frozen, reject unknown fields, and reject quoted
  strings where a native numeric scalar is required.
- Source conversions are explicit, versioned provenance. Historical
  probability-matrix conversions use `motif-conversion/v1`; position-specific
  count priors and explicit source-to-target background conversions use
  `motif-conversion/v2`. A target-background conversion must preserve both
  backgrounds and the selection policy, and its target must equal the model's
  scoring background. Compilation never applies a hidden second correction.
- DNA is uppercase `A/C/G/T`; coordinate spans are zero-based and half-open.
- A design has one exact fixed sequence length and an explicit positive target
  candidate count.
- Sequence length, candidate count, evaluator calls, evaluated bases, scoring
  operations, distance comparisons, portfolio bases, and canonical match rows
  have explicit public upper bounds. Feasibility checks do not materialize or
  exponentiate beyond those bounds.
- Each directional specification contributes exactly one best match per
  candidate under declared strand and deterministic tie-breaking rules. A seek
  satisfaction is the matched attainment; an avoid satisfaction is one minus
  that attainment. Versioned v2 hard avoidance constraints remain a separate
  legacy contract and are never silently converted to directions.
- One scoring implementation is authoritative. The v3 public balance score is
  the hard minimum of per-specification satisfaction; any smooth surrogate is
  search-internal and is never reported as the public score.
- Relative-attainment endpoints are exact extrema over one motif-width word.
  Best-window scanning preserves the reachable upper endpoint but can make the
  word-level lower endpoint unreachable as a sequence's reported match score.
- Candidate evaluation produces an immutable record. Search and selection may
  not mutate sequence or scores after that boundary.
- Selection returns exactly the requested count or fails explicitly. Diversity
  constraints cannot be silently relaxed.
- The complete best observed evaluation remains distinct from the constrained
  selected portfolio and is bound into every newly written manifest.
- Directional manifests record logarithmic satisfaction checkpoints, exact or
  bounded completion status, and no more than 256 deterministic unique elites.
- Candidate sequences and compact candidate identifiers are independently
  unique before construction, publication, and read-back.
- Equal scores have a stable total ordering independent of process scheduling,
  mapping order, locale, or host.
- Canonical output contains `design.json`, `motifs.json`, `candidates.tsv`,
  `matches.tsv`, and `manifest.json`. FASTA is a derived bundle member; review
  text, JSON, SVG, and HTML are generated on demand outside the bundle.
- Schema versions, scoring versions, seeds, budgets, and content digests are
  explicit in replayable artifacts.
- Attested execution verifies that the running package tree equals the
  retained wheel before and after search, then atomically publishes the resolved
  input, wheel, bundle, receipt, and execution index.
- Inspection defaults to the bundle contract, requires an explicit execution
  source mode, preserves delivery, search completion, and integrity as separate
  states, contains no source path, and accepts only current contracts.
- Supplied-candidate inspection replays a current directional candidate under
  explicit models without searching or verifying its origin. Its rank is
  caller-assigned, not a claim of portfolio membership or collection quality.

## Error channels

Malformed models, unsafe paths, impossible lengths, unknown fields, invalid
normalization domains, non-deterministic ties, insufficient feasible
candidates, and artifact-integrity failures raise explicit typed errors.
Scientific infeasibility is not converted to an empty successful portfolio.
Search-budget exhaustion, unresolved constraint feasibility, exhaustive proof
of constraint infeasibility, portfolio infeasibility, and the bounded
selection traversal limit are distinct typed failures.

## Change discipline

Add behavior with a failing contract test first. A public schema or score-
meaning change requires an architecture decision, compatibility statement,
negative tests, and reference-document updates. Optimizer improvements must not
change scoring or selection semantics accidentally.

Version `0.3` reads strict `run-manifest/v2` through `run-manifest/v4` and
writes only v4. Version `0.4` additionally reads v5 and writes only v5. V4 adds
the complete best observed evaluation without changing the selected-candidate
tables. Exact score replay pins the declared scoring, search, and selection
semantics. V5 binds the `relative_pwm_attainment_v2` scoring contract, v2 input
schemas, explicit target and avoider match roles, and avoider ceilings without
changing the target hard-minimum score. New v1 publication is prohibited.
Version `0.5` additionally reads v6. Directional `design-spec/v3` publication
writes v6 with satisfaction traces, exact-completion proof fields, and a bounded
elite reservoir; explicitly supplied v2 requests continue to write v5.
Earlier schemas require an explicit compatibility dispatcher; they are never
accepted through loosened validation.

## Search boundary

By default, small sequence spaces use deterministic exhaustive enumeration. Larger spaces
use `annealed_multistart_v1`, a bounded multi-start annealed stochastic local
search. It combines perturbed starts, four-base single-position resampling,
block and multi-base replacement, motif-guided proposals, and annealed
acceptance under one exact evaluator-call budget. It is a bounded optimizer,
not a probabilistic sampler. For directional runs it records logarithmic
checkpoints, per-specification satisfactions, limiting specifications, a bounded
elite reservoir, restart-final scores, and proposal counts rather than raw
optimizer-state traces. A fixed number of evaluator calls is not fixed compute: evaluation cost
still depends on sequence length, motif number and width, strand policy, and
avoiders.

That engine is production software, not evidence that it outperforms a
baseline. Comparative performance and repeated-seed robustness require a
separately frozen workflow over released package artifacts.

Directional Python calls can select `initialization="independent"`, recorded
as `annealed_independent_starts_v1`. Only the initialization changes: each chain
starts from an independent uniform DNA draw. The scientific request and
problem identity are unchanged; the engine and run identities differ. The
default remains related starts. Observation-on/off equivalence holds within
each method, and replay uses the recorded engine rather than an implicit
current default. Complete enumeration does not use initialization.

Directional Python calls also support explicit `method="greedy"` and
`method="random"` controls. Greedy uses the shared starts, strict hard-minimum
single-coordinate improvement, and no neutral moves or stagnation restarts.
It shares the default method's complete-enumeration shortcut. Random draws
independent whole sequences with replacement and never substitutes enumeration;
its recorded completion remains bounded, even when the budget exceeds the
space size. Both use the same scoring, accounting, retention, and selection.
The [method reference](docs/methods.md#explicit-comparison-methods) owns the
exact tie, partial-budget, initialization, and observation rules. Their
existence does not establish comparative performance.

Hard avoidance is feasibility-first. Search prefers feasible states before
optimizing target balance; among infeasible states it reduces the largest
ceiling excess. This is a lexicographic admission rule, not a weighted penalty.
Complete enumeration can prove constraint infeasibility. A bounded heuristic
run can report only that it exhausted its budget without finding enough
feasible sequences.

The directional public objective is a max-min formulation: maximize the minimum
seek-or-avoid specification satisfaction. In a larger space, the heuristic reports
the best evaluations it observed under its budget; it does not establish that
the global max-min solution was reached.

For legacy v2 requests, the advanced `motif_balance.observation` module can produce one bounded,
immutable, path-free record of the complete unique evaluated pool. It exists
for explicit downstream analysis, is replay-verified, and is not part of
`Portfolio`, the canonical bundle, or the top-level scientific facade. An
advanced paired operation derives both the ordinary `Portfolio` and this
observation from one authoritative search result when an analysis needs both.
Directional v3 requests refuse complete-pool observation. They retain the
manifest's bounded elite archive and can separately request
[passive search observations](docs/reference/search-observations.md), including
bounded samples above declared quality thresholds. These do not change the
search, selected portfolio, or canonical bundle, and are not uniform samples
of the design space.
