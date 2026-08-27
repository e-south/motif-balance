---
doc_id: motif-balance-design-contracts
title: Motif Balance engineering contracts
intent: State public semantics, invariants, and change rules.
audience:
  - maintainers
  - API consumers
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-27
doc_type: explanation
---

# Motif Balance engineering contracts

## Public contracts

The public scientific vocabulary is `MotifModel`, `DesignSpec`, `MotifMatch`,
`Candidate`, `Portfolio`, `design(spec) -> Portfolio`, and `score(...)`.
`Evaluation`, `ResultInspection`, and `ResultCatalog` are internal or
operational typed records, not additional top-level scientific nouns.
Scientific inputs belong in an immutable `DesignSpec`; operational CLI options
may select output or validation behavior but cannot revise that specification.

## Invariants

- Public models are strict, frozen, and reject unknown fields.
- Source conversions are explicit `motif-conversion/v1` provenance. A
  probability-matrix prior mixture requires a positive weight and source motif
  identity; compilation never applies a hidden second correction.
- DNA is uppercase `A/C/G/T`; coordinate spans are zero-based and half-open.
- A design has one exact fixed sequence length and an explicit positive target
  candidate count.
- Sequence length, candidate count, evaluator calls, evaluated bases, scoring
  operations, distance comparisons, portfolio bases, and canonical match rows
  have explicit public upper bounds. Feasibility checks do not materialize or
  exponentiate beyond those bounds.
- Each motif contributes exactly one best match per candidate under declared
  strand and deterministic tie-breaking rules.
- One scoring implementation is authoritative. The public balance score is the
  hard minimum of per-motif normalized scores; any smooth surrogate is search-
  internal and is never reported as the public score.
- Candidate evaluation produces an immutable record. Search and selection may
  not mutate sequence or scores after that boundary.
- Selection returns exactly the requested count or fails explicitly. Diversity
  constraints cannot be silently relaxed.
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

## Change discipline

Add behavior with a failing contract test first. A public schema or score-
meaning change requires an architecture decision, compatibility statement,
negative tests, and reference-document updates. Optimizer improvements must not
change scoring or selection semantics accidentally.

Version `0.3` reads strict `run-manifest/v2` and `run-manifest/v3` inventories
and writes only v3. Exact score replay pins the declared scoring, search, and
selection semantics. Earlier schemas require an explicit compatibility
dispatcher; they are never accepted through loosened validation.

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
