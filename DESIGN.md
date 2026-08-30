---
doc_id: motif-balance-design-contracts
title: Motif Balance engineering contracts
intent: State public semantics, invariants, and change rules.
audience:
  - maintainers
  - API consumers
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-29
doc_type: explanation
---

# Motif Balance engineering contracts

## Public contracts

The public scientific vocabulary is `MotifModel`, `DesignSpec`, `MotifMatch`,
`Candidate`, `Portfolio`, `design(spec) -> Portfolio`, and `score(...)`.
`Evaluation` and `ResultInspection` are internal or operational typed records,
not additional top-level scientific nouns.
Scientific inputs belong in an immutable `DesignSpec`; operational CLI options
may select output or validation behavior but cannot revise that specification.

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
- Each target motif contributes exactly one best match per candidate under
  declared strand and deterministic tie-breaking rules. Versioned hard
  avoidance constraints separately cap the best normalized match of each
  avoider motif; avoider scores never enter the target hard minimum.
- One scoring implementation is authoritative. The public balance score is the
  hard minimum of per-motif normalized scores; any smooth surrogate is search-
  internal and is never reported as the public score.
- Candidate evaluation produces an immutable record. Search and selection may
  not mutate sequence or scores after that boundary.
- Selection returns exactly the requested count or fails explicitly. Diversity
  constraints cannot be silently relaxed.
- The complete best observed evaluation remains distinct from the constrained
  selected portfolio and is bound into every newly written manifest.
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
Earlier schemas require an explicit compatibility dispatcher; they are never
accepted through loosened validation.

## Search boundary

Small sequence spaces use deterministic exhaustive enumeration. Larger spaces
use `annealed_multistart_v1`, which combines perturbed multi-chain starts, Gibbs-style
single-base updates, block and multi-base proposals, motif insertion, targeted
proposal windows, and annealed acceptance under one exact evaluator-call
budget. It records bounded checkpoints, restart-final scores, and proposal
counts rather than raw optimizer-state traces.

That engine is production software, not evidence that it outperforms a
baseline. Comparative performance and repeated-seed robustness require a
separately frozen workflow over released package artifacts.

Hard avoidance is feasibility-first. Search prefers feasible states before
optimizing target balance; among infeasible states it reduces the largest
ceiling excess. This is a lexicographic admission rule, not a weighted penalty.
Complete enumeration can prove constraint infeasibility. A bounded heuristic
run can report only that it exhausted its budget without finding enough
feasible sequences.

The advanced `motif_balance.observation` module can produce one bounded,
immutable, path-free record of the complete unique evaluated pool. It exists
for explicit downstream analysis, is replay-verified, and is not part of
`Portfolio`, the canonical bundle, or the top-level scientific facade. An
advanced paired operation derives both the ordinary `Portfolio` and this
observation from one authoritative search result when an analysis needs both.
