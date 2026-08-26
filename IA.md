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
last_verified: 2026-08-26
doc_type: reference
---

# Motif Balance information architecture

Motif Balance has one product ontology. It accepts a balanced motif design,
compiles explicit motif models, evaluates fixed-length sequences, searches a
bounded sequence space, selects an exact portfolio, and publishes a verifiable
bundle. Repository history and former workspace terminology are not part of
this ontology.

## Authorities

| Question | Authority | Versioned identity |
| --- | --- | --- |
| What is being requested? | `DesignSpec` | `design-spec/v1` |
| What does a motif mean? | `MotifModel` | `motif-model/v1` |
| How is a sequence scored? | compile and scoring | `normalized_llr_v1` |
| Which match wins? | scoring | `leftmost_plus_first_v1` |
| What is the joint score? | scoring | `weakest_score_v1` |
| How are sequences proposed? | `SearchEngine` | engine name and version |
| Which evaluated sequences ship? | selection | exact count and declared distance |
| What crosses a repository boundary? | canonical bundle | `run-manifest/v2` |
| Which released bytes performed a run? | execution workspace | `motif-balance.execution-workspace/v1` |
| Is a result accepted as evidence? | Research Studies | study evidence record |
| How is accepted evidence presented? | `manufold` | digest-pinned manuscript snapshot |
| Where are bulk executions retained? | storage | storage object manifest |

Storage owns location, retention class, and object closure. It does not define
score meaning, candidate meaning, study acceptance, or manuscript claims.

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

An evidence-producing execution wraps the resolved specification, exact wheel,
canonical bundle, runtime receipt, and content index in one independently
verifiable execution workspace. This is a product artifact, not a federated
workspace: it has no implicit active state, sibling-repository references,
mutable cache, or study or manuscript authority.

## Product and evidence boundaries

- Motif Balance owns reusable semantics, execution, and bundle verification.
- Storage owns durable placement and retention metadata for execution objects.
- Research Studies owns task cohorts, baselines, repeats, claim gates, and
  accepted evidence.
- `manufold` owns figure composition, captions, prose, builds, and handoffs.

No owner imports another repository's runtime source. Owners exchange released
software, versioned schemas, content digests, and immutable snapshots.

## Progressive documentation

Readers enter through [the documentation index](docs/index.md), then follow only
the route their task requires:

- concepts and first design for users;
- model, specification, and result references for scientific interpretation;
- public contract and bundle verification for integrators;
- this IA, [architecture](ARCHITECTURE.md), and [engineering contracts](DESIGN.md)
  for maintainers;
- the isolated [migration note](docs/migration/cruncher-sample-cutover.md) only
  for cutover reviewers.

The migration note may name former systems to classify parity and deprecation.
Those names must not expand the public API, normal configuration, or product
documentation tree.
