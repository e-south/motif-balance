---
doc_id: motif-balance-exhaustive-pairwise-example
title: Exhaustive pairwise example
intent: Exercise the exact-small-space path through the public CLI and bundle contract.
audience:
  - users
  - maintainers
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-08
doc_type: tutorial
---

# Exhaustive pairwise example

The current `design-spec/v3` request supplies two `seek` requirements. Change a
direction to `avoid` to ask for a weak strongest match to that model instead;
this changes the design problem, not just its display.

This sanitized exact-small-space example makes the balancing problem visible. Two constructed
motifs prefer different two-base sequences, while every candidate has room for only one
two-base window. Exhaustive search evaluates all 16 sequences and returns three distinct
candidates, including balanced compromises rather than a hidden reverse-complement shortcut.
The fixtures are not biological models, and their outputs support no biological claim.

```bash
motif-balance design examples/synthetic-pairwise/design.yaml --check
motif-balance design examples/synthetic-pairwise/design.yaml --out result
motif-balance inspect result
motif-balance inspect result --format html --out review.html
motif-balance inspect result --format svg --view candidate --out candidate.svg
```

Open `review.html` for the linear review, or use `candidate.svg` as the smaller
working artifact. Both are derived after verification and do not alter the
bundle. [candidate-review.svg](candidate-review.svg) is the committed output for
this exact fixture; the documentation gate regenerates it byte for byte.
