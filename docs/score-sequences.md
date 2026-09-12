---
doc_id: motif-balance-score-sequences
title: Score an existing sequence
intent: Evaluate one caller-supplied sequence through the authoritative public score operation.
audience:
  - API consumers
  - users
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-09
doc_type: how-to
journey:
  - score
---

# Score an existing sequence

Use the CLI when you already have a sequence and need the same matching and
score semantics used by design:

```bash
motif-balance score examples/synthetic-pairwise/design.yaml AT
motif-balance score examples/synthetic-pairwise/design.yaml AT \
  --format json --out score.json
```

The Python verb accepts an already constructed `DesignSpec`. Start with the
[complete Python tutorial](python-api.md) if you do not have one yet:

```python
from motif_balance import score

evaluation = score("AT", spec)  # spec.length must be 2 for this example

print(evaluation.balance_score)
for match in evaluation.matches:
    print(match.motif_id, match.spec_direction, match.normalized_score, match.spec_satisfaction)
```

Input DNA is case-insensitive and canonical records are uppercase `A/C/G/T`.
The sequence must contain exactly `spec.length` bases and no other symbols.
Invalid input raises
`motif_balance.errors.InvalidSequence`. The returned `Evaluation` is immutable,
contains exactly one deterministic best match per motif, and uses the same
hard-min balance score as candidate design.

Scoring evaluates only the supplied sequence; it does not generate or select a
portfolio. The saved request's count, seed, search budget and minimum portfolio
distance do not affect its score. Even a count larger than the complete sequence
space does not prevent scoring; `design` still rejects that impossible request.
The `DesignSpec` must satisfy its schema and resource limits, every motif must
fit, and the supplied DNA must match the declared length and alphabet. Hard
avoidance constraints, when explicitly present in a v2 request, are still
evaluated and reported; they are not removed with the portfolio-count check.

`--out` requires a new file in an existing writable directory. An occupied path
is rejected before evaluation, including a dangling symlink. Publication also
refuses a path created while scoring; it never replaces another caller's file.

Scores are comparable only under identical motif content and semantic versions.
See [interpreting results](interpreting-results.md) before assigning meaning to
their magnitude.
