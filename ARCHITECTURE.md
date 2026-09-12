---
doc_id: motif-balance-architecture
title: Motif Balance architecture
intent: Define ownership, dependency direction, and module boundaries.
audience:
  - maintainers
  - agent executors
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-09
doc_type: explanation
journey:
  - maintain
---

# Motif Balance architecture

Motif Balance is a standalone modular monolith: one repository, one Python
distribution, one public facade, and no runtime dependency on caller
repositories. The canonical ontology, semantic versions, and cross-owner
artifact boundaries are defined in [the information architecture](IA.md).

## Product boundary

The reusable product spine is:

```text
DesignSpec -> compile -> evaluate -> search -> select -> Portfolio -> artifact bundle
```

Motif Balance owns strict motif, direction, and design contracts, deterministic motif
matching and normalization, bounded candidate search, immutable evaluated
candidates, deterministic portfolio selection, and verifiable artifacts. It
does not own source-data curation, comparison design, claim acceptance,
presentation, raw optimizer traces, or artifact retention. Callers own those
concerns and cross this boundary only through explicit inputs or immutable
verified artifacts.

## Layer direction

```text
errors, constants, claim-language advisory, and model
  <- formats, compile, scoring, admissibility, and assessment
  <- search, selection, and alternatives
  <- api, artifacts, and observation
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
- `claim_language.py` is a pure, advanced wording-hazard seam for downstream
  study and manuscript authors. It does not inspect evidence, search literature,
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
- `admissibility.py` applies hard constraint status and feasibility-first
  ordering without changing the target score.
- `assessment.py` exposes the explicit `assess_pair` submodule API for
  pre-search seek-pair conflicts. It uses compiled log-odds, returns a bounded
  relative-arrangement profile, and cannot import search, selection, artifacts,
  or caller-owned study code. `model/assessment.py` owns its immutable records.
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
  rescore them.
- `alternatives/` owns the explicit supplied-pool architecture-ranking API.
  `api` admits and canonicalizes sequences, scores each equivalence class once,
  and ranks unchanged evaluations. It can also measure an explicit complete
  representative order without rescoring. `geometry` measures separate pair distances;
  `model/alternatives.py` owns strict records and selected-site equivalence.
  It cannot invoke search, publish artifacts, or import caller-owned analyses.
  Its ranked prefixes do not replace the distance-constrained portfolio selector.
- `artifacts/` serializes canonical bundles and replays their identities and
  scientific records. `encoding` owns canonical bytes and identities; `decoding`
  reconstructs strict records; `snapshot` pins bounded reads to file descriptors;
  `verification` replays scientific semantics; `publication` owns atomic
  no-replace writes. The facade preserves callers' existing imports. None of
  these modules owns downstream registration or presentation.
- `observation.py` owns the bounded, immutable complete evaluated-pool export
  for explicit legacy-v2 analysis consumers. Directional v3 runs use the
  manifest's bounded elite snapshot. Observation does not enlarge `Portfolio`, write into
  canonical bundles, discover storage, or enter the top-level facade.
  Its advanced paired operation may reuse the API shell's private portfolio
  construction from the same search result; it does not introduce another
  scoring, search, or selection authority.
- `api.py` owns `design`, `score`, and `Portfolio` publication for the top-level
  scientific facade. Its explicitly imported observation helpers derive a
  portfolio and bounded diagnostics from one search, or replay caller-owned
  observations. They add no top-level scientific verbs or CLI journeys.
- `receipt.py` defines the runtime receipt and execution-workspace identity
  without changing canonical bundle identity.
- `execution.py` owns exact-wheel validation, runtime attestation, receipts,
  and atomic execution-workspace publication. It does not discover stores or
  choose scientific policy.
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
- `cli/` registers the four public command journeys. `assessment`, `design`,
  `scoring`, and `inspection` are thin file/argument adapters to their owning
  APIs. `preparation` holds the hidden motif/execution adapters; `errors` and
  `output` share diagnostic and atomic no-replace publication behavior.
  The package entrypoint remains `motif_balance.cli:app`; no command owns
  scientific derivations or imports caller repositories.

`scripts/check_architecture.py` enforces this direction for absolute and
relative imports and fails on unknown first-party modules. Add a new layer only
with an explicit architecture update and tests.

## Deployment boundary

The package produces versioned artifacts. Callers exchange those artifacts,
digests, and explicit external references; they do not import each other's
source trees. Placement and retention are caller concerns and do not change
product identities or semantics.
