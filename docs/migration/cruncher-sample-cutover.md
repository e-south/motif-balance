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
