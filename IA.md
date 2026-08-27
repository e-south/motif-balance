---
doc_id: motif-balance-information-architecture
title: Motif Balance information architecture
intent: Define the canonical ontology, semantic authorities, artifacts, and owner boundaries.
audience:
  - maintainers
  - API consumers
  - evidence producers
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-27
doc_type: reference
---

# Motif Balance information architecture

Motif Balance has one product ontology. It accepts a balanced motif design,
compiles explicit motif models, evaluates fixed-length sequences, searches a
bounded sequence space, selects an exact portfolio, and publishes a verifiable
bundle. The ontology is deliberately limited to concepts required to perform,
verify, or inspect that operation.

## Authorities

| Question | Authority | Versioned identity |
| --- | --- | --- |
| What is being requested? | `DesignSpec` | `design-spec/v1` |
| What does a motif mean? | `MotifModel` | `motif-model/v1` |
| How did source values become positive probabilities? | `MotifConversion` | `motif-conversion/v1` |
| How is a sequence scored? | compile and scoring | `normalized_llr_v1` |
| Which match wins? | scoring | `leftmost_plus_first_v1` |
| What is the joint score? | scoring | `weakest_score_v1` |
| How are sequences proposed? | `SearchEngine` | engine name and version |
| Which evaluated sequences ship? | selection | exact count and declared distance |
| What crosses a repository boundary? | canonical bundle | `run-manifest/v2` |
| Which released bytes performed a run? | execution workspace | `motif-balance.execution-workspace/v1` |
| How is one result explained without mutation? | result inspection | `motif-balance.result-inspection/v1` |
| How are explicit result references browsed together? | derived result catalog | `motif-balance.result-catalog/v1` |

## Ontology

```text
MotifModel[] + length + count + strands + evaluations + seed + min_distance
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
total order, normalizes that match against the motif's null mean and consensus
score, and reports the lowest normalized motif score as `balance_score`.

The smooth minimum exists only inside search. It is never serialized as a
candidate score or interpreted as scientific evidence.

Source conversion is provenance, not a scoring alternative. A caller may
supply an already-positive probability model, a JASPAR count conversion, or a
probability matrix mixed with an explicit positive background prior. The latter
uses `(p_source + prior_weight * background) / (1 + prior_weight)` and records
`probability_matrix_prior_mixture_v1`. Design applies no further smoothing.
Source acquisition, motif choice, and conversion rationale remain caller-owned.

### Search

`evaluations` counts calls to the authoritative evaluator. Tractable spaces use
complete enumeration. Larger spaces use versioned multi-start annealed search
with single-base, block, multi-base, and motif-insertion proposals. The engine
records bounded checkpoints, restart-final scores, and proposal summaries; raw
state traces are not product artifacts.

### Selection

Selection ranks immutable evaluations by descending balance score and then
sequence. It applies the declared distance rule without relaxation. It returns
the exact requested count or raises a structured `SearchExhausted` error.

## Artifact contract

The canonical bundle contains:

```text
design.json
motifs.json
candidates.tsv
matches.tsv
manifest.json
```

`candidates.fasta` and `report.html` are derived, verified views. Every member
except the manifest is bound by relative path, byte count, and SHA-256 digest.
The bundle identity binds scientific inputs, search provenance, bounded
diagnostics, and artifact records. Publication is atomic and refuses an
existing destination.

An attested execution wraps the resolved specification, exact wheel,
canonical bundle, runtime receipt, and content index in one independently
verifiable execution workspace. It has no implicit active state, repository
references, mutable cache, discovery behavior, or interpretation authority.

Inspection is an on-demand projection over a verified bundle or execution. It
does not become a bundle member and cannot create a circular artifact identity.
A result catalog joins only explicit inspection records; it does not discover
Storage, choose a benchmark cohort, or accept evidence. These operational views
expose the product ontology without adding another scientific noun or workspace
authority.

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
- [result inspection](docs/reference/result-inspection.md) for read-only review
  and explicit catalogs;
- this IA, [architecture](ARCHITECTURE.md), and [engineering contracts](DESIGN.md)
  for maintainers.
