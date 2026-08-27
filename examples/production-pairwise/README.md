---
doc_id: motif-balance-production-pairwise-example
title: Production pairwise example
intent: Exercise the bounded annealed engine through the public CLI and bundle contract.
audience:
  - users
  - maintainers
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
doc_type: tutorial
---

# Production pairwise example

This sanitized example is large enough to select `annealed_multistart_v1`
instead of exhaustive enumeration. It proves the product path, exact count,
fixed length, bundle verification, and attested execution route. Its constructed
motifs support no biological claim.

```bash
motif-balance design examples/production-pairwise/design.yaml --check
motif-balance design examples/production-pairwise/design.yaml --out result
motif-balance verify result
motif-balance execute examples/production-pairwise/design.yaml \
  --release-artifact dist/motif_balance-0.2.0a2-py3-none-any.whl \
  --producer-revision <40-character-release-commit> \
  --out execution-workspace
```

The wheel must byte-match the running package tree. Read the trusted identities
from the producer release record or Storage object manifest, not from the
workspace being checked, and pass them to `motif-balance verify-execution`.
