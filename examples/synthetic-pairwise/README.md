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

This sanitized exact-small-space example makes the balancing problem visible. Two constructed
motifs prefer different two-base sequences, while every candidate has room for only one
two-base window. Exhaustive search evaluates all 16 sequences and returns three distinct
candidates, including balanced compromises rather than a hidden reverse-complement shortcut.
The fixtures are not biological models, and their outputs support no biological claim.

```bash
motif-balance design examples/synthetic-pairwise/design.yaml --check
motif-balance design examples/synthetic-pairwise/design.yaml --out result
motif-balance verify result
motif-balance inspect result --kind bundle --format html --out review.html
```

Open `review.html` to follow the method, see every best-match span on the shared candidate
coordinate axis, compare motif scores within the returned portfolio, and inspect recorded
best-so-far checkpoints. The review is derived after verification and does not alter the bundle.
