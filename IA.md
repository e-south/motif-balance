---
doc_id: motif-balance-information-architecture
title: Motif Balance information architecture
intent: Define the canonical ontology, semantic authorities, artifacts, and owner boundaries.
audience:
  - maintainers
  - API consumers
  - downstream integrators
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-30
doc_type: reference
---

# Motif Balance information architecture

Motif Balance has one product ontology for balanced inverse design. It accepts
explicit motif models and a fixed sequence length, evaluates candidate
sequences, searches a bounded sequence space, selects an exact portfolio, and
publishes a verifiable bundle. The best-scoring sequence realization for each
motif—its matched word, placement, strand, and any shared coordinates—emerges
from candidate evaluation rather than being prescribed. The ontology is
deliberately limited to concepts required to perform, verify, or inspect that
operation.

## Authorities

| Question | Authority | Versioned identity |
| --- | --- | --- |
| What is being requested? | `DesignSpec` | `design-spec/v2` (v1 read-only) |
| What does a motif mean? | `MotifModel` | `motif-model/v2` (v1 read-only) |
| How did source values become positive probabilities? | `MotifConversion` | `motif-conversion/v1` or `motif-conversion/v2` |
| How is a sequence scored? | compile and scoring | `relative_pwm_attainment_v2` |
| Which match wins? | scoring | `leftmost_plus_first_v1` |
| What is the joint score? | scoring | `weakest_score_v1` |
| How are sequences proposed? | `SearchEngine` | engine name and version |
| Which evaluated sequences ship? | selection | exact count and declared distance |
| What crosses a repository boundary? | canonical bundle | `run-manifest/v5` |
| Which released bytes performed a run? | execution workspace | `motif-balance.execution-workspace/v1` |
| How is one result explained without mutation? | `ResultInspection` | `motif-balance.result-inspection/v4` |

## Ontology

```text
target MotifModel[] + optional avoider ceilings + design fields
                                │
                                ▼
                           DesignSpec
                                │
                                ▼
                         CompiledProblem
                                │
                 ┌──────────────┴──────────────┐
                 ▼                             ▼
             Evaluation                  SearchEngine
       sequence + best matches       bounded proposal process
                 │                             │
                 └──────────────┬──────────────┘
                                ▼
                           Candidate[]
                                │
                                ▼
                            Portfolio
                                │
                                ▼
                     canonical result bundle
```

An `Evaluation` is the immutable boundary. Search may propose another sequence
and selection may choose among evaluations, but neither may alter an evaluated
sequence, match, or score. A `Portfolio` contains exactly `DesignSpec.count`
fixed-length candidates or the operation fails.

## Semantic contracts

### Scoring

Each motif is a positive position-by-base probability matrix with an explicit
background. Compilation derives log-odds scores. Evaluation scans every valid
offset and declared strand, selects one match per motif with a deterministic
total order, and reports its relative attainment between the motif's theoretical
minimum and maximum raw log-likelihood-ratio scores over one motif-width word.
Both word-level extrema are exact; after retaining the best score across
multiple placements or orientations, the lower endpoint need not be
sequence-attainable while the upper endpoint remains attainable by embedding a
maximizing word. The
conventional probability consensus is recorded separately from the
score-maximizing reference because they can differ under a nonuniform
background. The lowest relative attainment is `balance_score`. Avoider motifs
use the same scanner but have
explicit upper ceilings; their scores and violations are separate records and
never enter the target hard minimum. V2 snaps only endpoint-scale numerical
excursions within tolerance and fails closed beyond it.

The smooth minimum exists only inside search. It is never serialized as a
candidate score or treated as accepted study support.

Source conversion is provenance, not a scoring alternative. A caller may
supply an already-positive probability model, a JASPAR count conversion, or a
probability matrix mixed with an explicit positive background prior. New count
conversion uses a position-specific background-weighted prior with
`alpha_i = sqrt(N_i)` and records
`motif-conversion/v2` with `count_matrix_sqrt_n_background_prior_v1`.
Probability-matrix conversion uses
`(p_source + prior_weight * background) / (1 + prior_weight)` and records
`probability_matrix_prior_mixture_v1`; it never fabricates an effective count.
Design applies no further smoothing. Source acquisition, motif choice, and
conversion rationale remain caller-owned.

### Search

`evaluations` counts calls to the authoritative evaluator. Tractable spaces use
complete enumeration. Larger spaces use versioned multi-start annealed search
with single-base, block, multi-base, and motif-insertion proposals. The engine
records bounded checkpoints, restart-final scores, and proposal summaries; raw
state traces are not product artifacts. Complete enumeration establishes an
optimum only when the admitted sequence space is fully covered. Annealed runs
publish the best result observed under their declared evaluator-call budget,
not a convergence or global-optimality claim.

Hard avoidance is feasibility-first: feasible evaluations outrank infeasible
evaluations before target score is considered. Among infeasible evaluations,
search prefers smaller maximum ceiling excess. This lexicographic contract is
not a weighted penalty. Exhaustive search can prove exact constraint
infeasibility; bounded search can report only unresolved feasibility at its
declared budget.

Shared coordinates between representative target matches are inspectable
sequence geometry. They do not establish simultaneous motif occupancy,
co-binding, or regulatory function.

### Selection

Selection ranks immutable evaluations by descending balance score and then
sequence. It applies the declared distance rule without relaxation. It returns
the exact requested count or raises a typed `SearchBudgetExhausted`,
`ConstraintFeasibilityExhausted`, `ExactConstraintInfeasible`,
`PortfolioInfeasible`, or `SelectionLimitReached` failure. The last state means
the bounded subset traversal did not resolve feasibility; it is not proof that
no feasible portfolio exists.

The best observed evaluation and the selected portfolio are distinct records.
The manifest retains the complete score-ranked best evaluation even when a
distance constraint excludes that sequence from the exact selected set.
`candidates.tsv`, `matches.tsv`, and FASTA contain only selected portfolio
members. Older readable manifests may expose only the best observed score
because they did not retain the corresponding sequence and matches.

## Artifact contract

The canonical bundle contains:

```text
design.json
motifs.json
candidates.tsv
matches.tsv
manifest.json
```

`candidates.fasta` is a derived, verified bundle member. Every member except
the manifest is bound by relative path, byte count, and SHA-256 digest.
The bundle identity binds scientific inputs, the complete best observed
evaluation, search provenance, bounded diagnostics, and artifact records.
Publication is atomic and refuses an existing destination.

An attested execution wraps the resolved specification, exact wheel,
canonical bundle, runtime receipt, and content index in one independently
verifiable execution workspace. It has no implicit active state, repository
references, mutable cache, discovery behavior, or interpretation authority.

Text, inspection JSON, SVG, and HTML are on-demand review projections and
never enter the bundle.

A separately requested `evaluated-pool-observation/v2` can carry the complete
unique evaluated pool to an analysis owner. It is bounded, immutable,
identity-checked, scientifically replayed, and path-free. Each unique row
records its first authoritative evaluator-call index, and verification reruns
the deterministic search to establish row coverage, discovery order, counts,
checkpoints, and diagnostics. The advanced paired operation can derive it and
the ordinary portfolio from the same search result. It is not a bundle
member, public `Portfolio` field, ordinary CLI journey, or top-level noun.

Inspection is one immutable typed projection over a verified bundle or
execution. Verification and score replay produce `ResultInspection`; every
renderer consumes only that projection. A renderer cannot read a workspace,
rescan a sequence, recompute a score, contact a network, compare runs, or
accept evidence. It therefore cannot create a circular artifact identity.
Inspection is deliberately limited to one explicit result. Joining results,
discovering Storage, choosing a benchmark cohort, and accepting evidence remain
outside the package.

## Product boundary

- Motif Balance owns reusable semantics, bounded execution, artifacts,
  verification, and single-result inspection.
- Callers own model-source choice, task cohorts, comparisons, repetitions,
  acceptance criteria, and downstream claims.
- Artifact stores own placement, retention, and discovery without changing
  result meaning.

Integration occurs through released software, versioned schemas, content
digests, and immutable artifacts—not runtime source imports.

## Progressive documentation

Readers enter through [the documentation index](docs/index.md), then follow only
the route their task requires:

- concepts and first design for users;
- model, specification, and result references for scientific interpretation;
- public contract and bundle verification for integrators;
- [result inspection](docs/reference/result-inspection.md) for read-only review;
- this IA, [architecture](ARCHITECTURE.md), and [engineering contracts](DESIGN.md)
  for maintainers.
