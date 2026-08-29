---
doc_id: motif-balance-design-spec
title: Design specification reference
intent: Define every design-spec/v2 field, input rule, and resource bound.
audience:
  - API consumers
  - CLI users
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-29
doc_type: reference
---

# Design specification reference

`DesignSpec` is the complete immutable design request. Unknown fields,
duplicate YAML or JSON keys, booleans used as numbers, and non-finite numeric
values fail validation. Numeric fields must use native numbers; quoted values
such as `length: "20"` or `min_distance: "0.2"` are rejected.

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `schema_version` | `design-spec/v2` | no | Defaults to `design-spec/v2`. |
| `motifs` | nonempty mapping | yes | Key is the motif ID; value is an inline model or contained relative path. |
| `avoiders` | mapping | no | Key is an avoider motif ID; value supplies `motif` and a `score_ceiling` from 0 to 1. |
| `length` | integer, 1–10,000 | yes | Exact candidate length in bases. |
| `count` | integer, 1–100,000 | yes | Exact number of distinct candidates to return. |
| `strands` | `forward` or `both` | no | Defaults to `both`. |
| `evaluations` | integer, 1–100,000 | yes | Authoritative evaluator-call budget; must be at least `count`. |
| `seed` | nonnegative integer | yes | Seed for deterministic search. |
| `min_distance` | number, 0–1 or null | no | Minimum normalized Hamming distance; null and zero are unconstrained. |
| `scoring_semantics` | `relative_pwm_attainment_v2` | no | Fixed scoring authority. |
| `objective_semantics` | `weakest_score_v1` | no | Fixed hard-min public objective. |
| `tie_break_semantics` | `leftmost_plus_first_v1` | no | Fixed best-match total order. |

Minimal serialized form:

```yaml
schema_version: design-spec/v2
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

## Hard avoidance constraints

`design-spec/v2` adds hard upper bounds on avoider motifs:

```yaml
schema_version: design-spec/v2
motifs:
  desired: motifs/desired.yaml
avoiders:
  off_target:
    motif: motifs/off-target.yaml
    score_ceiling: 0.35
length: 20
count: 8
strands: both
evaluations: 4096
seed: 7
min_distance: 0.2
```

The same scanner reports one best normalized match for every avoider. A
sequence is feasible only when every avoider score is at or below its ceiling.
Target and avoider identifiers must be disjoint. Avoider scores are recorded
separately and never enter `balance_score`; search admits feasibility before
optimizing the target hard minimum. Constraints are not weighted penalties.

Complete enumeration can prove that no sequence is feasible. A bounded search
that finds too few feasible sequences reports unresolved feasibility and does
not claim proof. A feasible pool can still fail exact-count portfolio selection
or reach the independent distance-selection node limit.

## Combined resource bounds

Validation also caps the work implied by otherwise valid fields:

- at most 1,000,000 candidate–motif rows across targets and avoiders;
- at most 10,000,000 selected portfolio bases;
- at most 25,000,000 evaluated bases;
- at most 100,000,000 motif-window base-score operations across targets and
  avoiders;
- at most 10,000,000 pairwise distance base comparisons when distance is positive.

These are product safety limits, not optimizer advice. Requests outside them
fail before search. A request within them can still fail: the evaluator budget
may produce too few unique candidates, the complete evaluated pool may contain
no distance-feasible subset, or the bounded subset traversal may reach its node
limit before resolving feasibility. Each state has a distinct typed error; none
returns a partial portfolio or weakens the distance rule.
