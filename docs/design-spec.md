---
doc_id: motif-balance-design-spec
title: Design specification reference
intent: Define every design-spec/v1 field, input rule, and resource bound.
audience:
  - API consumers
  - CLI users
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
doc_type: reference
---

# Design specification reference

`DesignSpec` is the complete immutable design request. Unknown fields,
duplicate YAML or JSON keys, booleans used as numbers, and non-finite numeric
values fail validation.

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `schema_version` | `design-spec/v1` | no | Defaults to `design-spec/v1`. |
| `motifs` | nonempty mapping | yes | Key is the motif ID; value is an inline model or contained relative path. |
| `length` | integer, 1–10,000 | yes | Exact candidate length in bases. |
| `count` | integer, 1–100,000 | yes | Exact number of distinct candidates to return. |
| `strands` | `forward` or `both` | no | Defaults to `both`. |
| `evaluations` | integer, 1–100,000 | yes | Authoritative evaluator-call budget; must be at least `count`. |
| `seed` | nonnegative integer | yes | Seed for deterministic search. |
| `min_distance` | number, 0–1 or null | no | Minimum normalized Hamming distance; null and zero are unconstrained. |
| `scoring_semantics` | `normalized_llr_v1` | no | Fixed scoring authority. |
| `objective_semantics` | `weakest_score_v1` | no | Fixed hard-min public objective. |
| `tie_break_semantics` | `leftmost_plus_first_v1` | no | Fixed best-match total order. |

Minimal serialized form:

```yaml
schema_version: design-spec/v1
motifs:
  motif_a: motifs/motif-a.yaml
  motif_b: motifs/motif-b.yaml
length: 20
count: 8
strands: both
evaluations: 4096
seed: 7
min_distance: 0.2
```

Relative motif references must stay inside the specification directory and may
not traverse symlinks. Mapping keys must equal each resolved model's
`motif_id`. Inline models follow the [motif-model contract](motif-models.md).

## Combined resource bounds

Validation also caps the work implied by otherwise valid fields:

- at most 1,000,000 candidate–motif rows;
- at most 10,000,000 selected portfolio bases;
- at most 25,000,000 evaluated bases;
- at most 100,000,000 motif-window base-score operations;
- at most 10,000,000 pairwise distance base comparisons when distance is positive.

These are product safety limits, not optimizer advice. Requests outside them
fail before search. A request within them can still be infeasible; design then
raises a typed failure rather than returning fewer candidates or weakening the
distance rule.
