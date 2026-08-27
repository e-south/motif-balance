---
doc_id: motif-balance-synthetic-multimotif-example
title: Annealed four-motif example
intent: Exercise one multi-motif design through the same public product contract.
audience:
  - users
  - maintainers
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
doc_type: tutorial
---

# Annealed four-motif example

This sanitized example exercises four explicit models through the ordinary
annealed-search, exact-selection, bundle, verification, and inspection path.
The motifs are constructed fixtures and carry no biological interpretation.

```bash
motif-balance design examples/synthetic-multimotif/design.yaml --check
motif-balance design examples/synthetic-multimotif/design.yaml --out result
motif-balance verify result
```
