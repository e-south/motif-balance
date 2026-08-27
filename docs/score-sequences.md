---
doc_id: motif-balance-score-sequences
title: Score an existing sequence
intent: Evaluate one caller-supplied sequence through the authoritative public score operation.
audience:
  - API consumers
  - users
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-27
doc_type: how-to
journey:
  - score
---

# Score an existing sequence

Use the CLI when you already have a sequence and need the same matching and
score semantics used by design:

```bash
motif-balance score examples/synthetic-pairwise/design.yaml ACGT
motif-balance score examples/synthetic-pairwise/design.yaml ACGT \
  --format json --out score.json
```

The Python verb accepts an already constructed `DesignSpec`:

```python
from motif_balance import score

evaluation = score("ACGT", spec)

print(evaluation.balance_score)
for match in evaluation.matches:
    print(match.motif_id, match.start, match.end, match.strand, match.normalized_score)
```

The sequence is uppercased, must contain exactly `spec.length` bases, and may
contain only `A`, `C`, `G`, and `T`. Invalid input raises
`motif_balance.errors.InvalidSequence`. The returned `Evaluation` is immutable,
contains exactly one deterministic best match per motif, and uses the same
hard-min balance score as candidate design.

Scores are comparable only under identical motif content and semantic versions.
See [interpreting results](interpreting-results.md) before assigning meaning to
their magnitude.
