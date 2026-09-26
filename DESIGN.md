---
doc_id: motif-balance-design-contracts
title: Design contracts
intent: State scientific invariants and change requirements.
audience: [maintainers, API consumers]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-20
doc_type: reference
---

# Design contracts

Scoring, search and selection have separate responsibilities. A user should be
able to change search effort or inspect a result without changing how a fixed
DNA sequence is evaluated. The contracts below preserve that property.

## Public operations

The top-level API exposes `MotifModel`, `MotifSpecification`, `DesignSpec`,
`MotifMatch`, `Candidate`, `Portfolio`, `design` and `score`.
[The public reference](docs/reference/public-contract.md) specifies their inputs,
outputs and supported versions. [Pair and joint assessment](docs/pair-assessment.md)
calculates local preference conflict before search; it is distinct from sequence
scoring. [Architecture ranking](docs/choose-alternatives.md) and
[portfolio selection](docs/reference/portfolio-selection.md) operate on supplied
sequences and cannot invoke sequence search.

## Invariants

The current supplied-pool [portfolio contract](docs/reference/portfolio-selection.md)
is `portfolio-policy/v1` and `portfolio-selection/v2`. It rescans canonical
literals and keeps the original generation request separate from the output
count. Exact count, selected-footprint or Hamming separation, and optional
distinct architecture are hard postconditions. Optimality, a feasible witness,
unresolved work, pool infeasibility, and a necessary architecture-bound refusal
are explicit results. There is no permissive reader, legacy adapter, or
automatic conversion from architecture-ranked prefixes.

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
  that attainment. Hard score ceilings are not part of this design contract.
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
Search-budget exhaustion, finite-pool portfolio infeasibility, and the bounded
selection traversal limit are distinct typed failures.

## Change discipline

Add behavior with a failing contract test first. A public schema or score-
meaning change requires an architecture decision, compatibility statement,
negative tests, and reference-document updates. Optimizer improvements must not
change scoring or selection semantics accidentally.

The reader and writer use only `design-spec/v3`, `motif-model/v2`, and
`run-manifest/v7`, with `relative_pwm_attainment_v2` scores and
`search-diagnostics/v4`. Every result retains the complete best observed
evaluation, satisfaction checkpoints, completion fields, and bounded elites.
Retired formats fail at intake; no compatibility dispatcher or automatic
conversion is shipped. Historical records remain bound to their original
software and are not rewritten.

## Search boundary

[Methods](docs/methods.md) defines enumeration, annealed search, greedy search,
uniform random sampling and their budget accounting. Those policies share the
same evaluator and immutable evaluations. A smooth search objective must never
replace the public hard minimum in candidate records.

Changing a method or initialization policy changes the run identity, not the
scoring problem. Observation must leave the RNG stream, evaluated sequences and
selected portfolio unchanged. A bounded run reports the best result evaluated
within its budget; only complete enumeration establishes a whole-space optimum.

## Post-design diversification

[Diversification](docs/diversify-sequences.md) preserves each desired model's
selected coordinates and strand under the canonical tie rule. Every desired
score loss and unwanted-score increase is bounded separately relative to the
parent. The complete Cartesian product is rescored before its template is
returned. The parent is included, flanks are fixed by default, and a parent-only
result remains explicit. Search, model preparation, and arrangement grouping
are unchanged. Diversification counts its own evaluations and records provenance.
