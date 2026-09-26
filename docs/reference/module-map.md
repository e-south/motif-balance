---
doc_id: motif-balance-module-map
title: Module responsibilities
intent: Locate implementation responsibilities and permitted dependencies.
audience: [maintainers]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-20
doc_type: reference
---

# Module responsibilities

```text
errors, constants, claim-language advisory, and model
  <- formats, compile, scoring, and assessment
  <- search, selection, and alternatives
  <- api and artifacts
  <- receipt and execution
  <- inspection/{verify, project, render}
  <- cli
```

- `model/` contains strict immutable public contracts and no higher-layer
  imports. Its facade preserves public imports; `base` owns canonical identity
  primitives, `motif` owns source models, `design` owns input contracts,
  `evaluation` owns scored candidates, `search` owns bounded diagnostics,
  `execution` owns runtime receipts, `manifest` owns run records, and `portfolio`
  owns cross-record consistency. These are contract domains, not plugin layers.
- `constants.py` contains only shared literal constants and imports no other
  first-party layer.
- `claim_language.py` is a pure, optional wording checker for downstream
  reports. It does not inspect evidence, search literature,
  rewrite text, or accept claims, and it is absent from the top-level facade and CLI.
- `formats/` parses external representations into strict models; it does not
  choose scientific policy.
- `compile.py` normalizes a specification into evaluator-ready state.
  Supplied-sequence scoring and pool ranking use `compile_scoring`, which checks motif widths and
  normalization without requiring the original portfolio count to be attainable.
  `compile_design` also checks that count before compiling matrices. Both routes
  share the same compilation and problem identity; neither changes the saved
  specification. This is an internal admission boundary, not another score formula.
- `scoring.py` is the single matching and public-score authority.
- `assessment/` exposes the explicit `assess_pair` and bounded `assess_motifs` submodule APIs for
  pre-search shared-base conflict. `pair` owns the complete pair profile; `joint`
  owns exact bounded placement of two to four models; `terms` is the single
  information-weighted local-loss calculation. Assessment cannot import search,
  selection, artifacts or study code. `model/assessment.py` owns its immutable records.
  Its structural score is not a sequence score or an achieved-outcome prediction.
- `search/` proposes sequences under explicit budgets. `engine` owns scheduling
  and acceptance, `moves` owns fixed-length proposals, `policy` owns the fixed
  annealing functions, and `recording` owns the search ledger and elite ranking.
  `initialization` owns shared starting sequences; `greedy` owns the explicit
  coordinate-improvement control; `uniform` owns whole-sequence random draws.
  They reuse scoring and recording, not study-specific experiment machinery.
  `observation` passively records bounded snapshots and exact target hits;
  `retention` implements bounded hash-priority samples at caller-declared quality
  thresholds. Neither draws randomness nor changes decisions. No search module
  reinterprets scores.
- `selection.py` chooses from already evaluated candidates and cannot mutate or
  rescore them. Its bounded bottleneck traversal consumes an admitted constraint
  graph and reports a full witness separately from finite-pool completion.
- `alternatives/` owns the explicit supplied-pool architecture-ranking API.
  `pool` admits and canonicalizes supplied sequences and records their counts.
  `api` ranks unchanged evaluations after scoring each equivalence class once. It can also measure an explicit complete
  representative order without rescoring. `geometry` measures separate pair distances;
  `model/alternatives.py` owns strict records and selected-site equivalence.
  It cannot invoke search, publish artifacts, or import caller-owned analyses.
  Its ranked prefixes do not replace the distance-constrained portfolio selector.
  `portfolio` supplies the current `select_portfolio` and replay boundary. It
  reuses pool admission, canonical scoring, and prepared geometry, then delegates
  unchanged evaluations to `selection`. `model/selection.py` owns its explicit
  policy and result. Neither a class-pruned pool nor caller-supplied scores are
  accepted as substitutes for the literal input pool. Selection never imports
  the higher-level alternatives orchestration.
- `variants/` owns deterministic post-design diversification. It reuses compilation
  and complete-sequence scoring, and never calls search or arrangement selection.
  `model/variants.py` owns immutable product-library and substitution records;
  `formats/variants.py` supplies FASTA and score tables. `variants.load_library` uses
  the bounded JSON parser and replays the complete construction before accepting
  saved scores and effort counts. The data-only variant
  renderer consumes these records directly. It cannot import the diversification
  API or scoring. The CLI is a thin adapter to these owners.
- `artifacts/` serializes canonical bundles and replays their identities and
  scientific records. `encoding` owns canonical bytes and identities; `decoding`
  reconstructs strict records; `snapshot` pins bounded reads to file descriptors;
  `verification` replays scientific semantics; `publication` owns atomic
  no-replace writes. The facade preserves callers' existing imports. None of
  these modules owns downstream registration or presentation.
- `api.py` owns `design`, `score`, and `Portfolio` publication for the top-level
  scientific facade. Its explicitly imported observation helpers derive a
  portfolio and bounded diagnostics from one search, or replay caller-owned
  observations. They add no top-level scientific verbs or CLI journeys.
- `receipt.py` defines the runtime receipt and execution-workspace identity
  without changing canonical bundle identity.
- `execution/` binds execution to a verified distribution. `release` verifies
  wheel contents, RECORD entries and the running package; `workspace_io` reads
  bounded descriptor snapshots and checks digests; `workspace` executes, publishes
  and verifies the workspace. These operations use explicit paths.
- `inspection/api.py` is the single advanced entry point for verifying and
  projecting one explicit bundle or execution workspace.
- `inspection/verify.py` carries the path-bound, already verified source into
  review without exposing it to renderers.
- `inspection/project.py` replays authoritative scores and projects candidates
  and their scoring problem. Bundle review produces `ResultInspection`.
- `inspection/supplied.py` exposes `inspect_candidate` for one explicit current
  `Candidate` and `DesignSpec`. It reuses scoring admission and projection, not
  search or bundle loading. Its path-free `CandidateInspection` is defined in
  the data-only `inspection/candidate_model.py`; it preserves caller-assigned
  rank without inventing a run, selected portfolio, or artifact trust state.
- `inspection/assessment/` computes a path-free pre-search column projection
  from two explicit models through the assessment authority. It cannot render
  or create a candidate. The projection retains model identity, relative
  placement and local regret in one physical base frame.
- `inspection/render/` turns these inspection projections into text, JSON, SVG, or one
  self-contained HTML composition. It cannot read artifacts, search, rescore,
  discover stores, compare cohorts, or accept evidence.
  The candidate renderer keeps `render/candidate.py` as its stable facade and
  separates verified candidate selection, deterministic layout, positional
  support, and SVG-section composition into candidate-named internal modules.
  The same candidate renderer accepts `ResultInspection` or `CandidateInspection`
  and clearly labels the latter's caller-supplied rank and replay-only scope.
  Renderers may import these data contracts, never the supplied-candidate replay
  operation. There is no scene graph, renderer registry, or second score authority.
  The pre-search renderer consumes only `inspection/assessment/model.py`, never
  its calculation entrypoint. It shares information-height Arial glyphs with
  the candidate renderer; it does not invent a sequence or observed bases.
- `cli/` registers the public commands. `assessment`, `design`, `collection`,
  `scoring`, and `inspection` are thin file/argument adapters to their owning
  APIs. `preparation` holds the hidden motif/execution adapters; `errors` and
  `output` share diagnostic and atomic no-replace publication behavior.
  The package entrypoint remains `motif_balance.cli:app`; no command owns
  scientific derivations or imports caller repositories.
  `collection` verifies a saved bundle through `artifacts` and delegates its
  retained sequences to `alternatives`; it performs no grouping or scoring itself.

`scripts/check_architecture.py` enforces this direction for absolute and
relative imports and fails on unknown first-party modules. Add a new layer only
with an explicit architecture update and tests.


Return to the [architecture overview](../../ARCHITECTURE.md).
