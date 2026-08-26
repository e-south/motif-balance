---
doc_id: motif-balance-exhaustive-pairwise-example
title: Exhaustive pairwise example
intent: Exercise the exact-small-space path through the public CLI and bundle contract.
audience:
  - users
  - maintainers
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
doc_type: tutorial
---

# Exhaustive pairwise example

This sanitized exact-small-space example proves the package path from a strict specification to
a verified bundle. Its motifs are constructed fixtures, not biological models, and its outputs
support no biological claim.

```bash
motif-balance design examples/synthetic-pairwise/design.yaml --check
motif-balance design examples/synthetic-pairwise/design.yaml --out result
```
