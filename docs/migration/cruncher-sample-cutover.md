---
doc_id: motif-balance-sample-cutover
title: Cruncher Sample cutover ledger
intent: Isolate the compatibility decisions needed to retire the former Sample surface.
audience:
  - maintainers
  - evidence producers
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
doc_type: decision
---

# Cruncher Sample cutover ledger

This is a migration record, not a second product architecture. The canonical
Motif Balance vocabulary and semantics live in [IA](../../IA.md).

## Preserve by contract

- explicit motif identity and content hashes;
- deterministic best-match coordinates, strand, and tie rules;
- normalized log-odds and the hard minimum across motifs;
- seeded bounded search with local, wider, targeted, and insertion proposals;
- deterministic deduplication, ordering, and portfolio selection;
- strict failure for invalid models, infeasible counts, occupied outputs, and
  corrupt artifacts.

## Correct intentionally

- final candidates remain the declared fixed length;
- final count is enforced after every operation;
- evaluated candidates are never polished or trimmed afterward;
- reverse-strand target coordinates are used once in genomic coordinates;
- distance constraints never relax silently;
- smooth-min values remain search-internal;
- manifests use relative paths, per-file digests, and bundle-level atomicity.

## Retire from the product boundary

Catalog fetching, workspace federation, posterior terminology, mandatory raw
traces, move-event logs, trajectory videos, duplicated elite formats, and
machine-specific paths do not belong to Motif Balance. Storage may retain bulk
comparison material without changing the package ontology.

## Cutover gates

1. Differential results are normalized and every difference is classified.
2. A released package reruns the frozen study cohort.
3. Storage objects retain verified execution workspaces and external trust anchors.
4. Downstream consumers use bundle adapters or their actual owning package.
5. Research Studies accepts evidence and `manufold` imports snapshots by digest.
6. Rollback to the preceding coherent package and artifact set is demonstrated.

Only then may the former Sample-specific routes contract. Unrelated former
package routes have independent owners and are not part of this cutover.

## Current gate state

| Gate | State | Evidence or blocker |
| --- | --- | --- |
| Product implementation | Complete for the repository-local v0.2 contract | Revision `6c92d1c` passes the complete source, wheel, execution, documentation, security, and adversarial gate. This does not establish legacy replacement or adoption. |
| Differential classification | Partial | The accepted fixed-sequence scoring tracer classifies one intentional epsilon-policy correction. Frozen-cohort optimizer and portfolio comparisons remain study-owned and incomplete. |
| Released-cohort rerun | Blocked | The v0.2 package has no named private release, and the benchmark cohort is not frozen. |
| Storage handoff | Complete for product dogfood only | Exact and annealed example workspaces validate under both the product and Storage contracts. They are not accepted benchmark evidence. |
| Consumer adoption | Blocked | No downstream consumer may pin an unpublished or workspace-relative package. Consumer-specific dispositions are below. |
| Evidence and manuscript handoff | Partial | The scoring record is producer-available; its manuscript snapshot is pending. Benchmark evidence remains blocked. |
| Rollback and contraction | Blocked | No released v0.2 adoption or downstream rollback has been demonstrated. Sample routes remain in place. |

## Consumer disposition

| Consumer | Disposition | Required next artifact |
| --- | --- | --- |
| BaseRender | First eligible Sample consumer after a private release. Add a BaseRender-owned `motif_balance_bundle` adapter beside the existing legacy adapter. | Pinned v0.2 dependency, immutable v2 bundle fixture, expected bundle identity, adapter tests, and rollback to `cruncher_best_window`. |
| DenseGen | Not a direct Sample-design cutover. It currently consumes Cruncher multi-motif parsing and catalog metadata that Motif Balance deliberately does not own. | A data-owner or DenseGen-owned motif-collection contract; do not add catalog fetching to Motif Balance. |
| YIU | Not a drop-in replacement. Its views can require multiple motif occurrences, whereas Motif Balance publishes one authoritative best match per motif and candidate. | A versioned YIU input subtype with explicit occurrence semantics and trusted bundle identity. |
| Sample-backed Cruncher Study and Portfolio | Part of the contraction inventory, but not code to port into Motif Balance. Their sweeps and portfolio recipes depend on Sample exports. | Promote required benchmark recipes to Research Studies, prove parity and rollback, then retire or reroute the legacy paths. |
| USR promoter, Cassette, and non-Sample payload routes | Outside the Sample cutover. Their behavior has separate owners. | Independent extraction or retirement decisions under those owners. |

The next executable cutover slice begins only after the v0.2 private release
provides a dependency and checksum that BaseRender can pin. Until then, keeping
the verified legacy adapter is rollback capacity, not a reason to copy legacy
workspace semantics into Motif Balance.
