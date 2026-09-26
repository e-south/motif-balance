---
doc_id: motif-balance-design-spec
title: Design specification reference
intent: Define directional design inputs and their resource bounds.
audience: [API consumers, CLI users]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-20
doc_type: reference
---

# Design specification reference

A design request specifies which motifs to seek or avoid, how much DNA is
available and how many sequences to return. Store it as YAML or JSON, or construct
a `DesignSpec` in Python. The current file schema is `design-spec/v3`.

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `schema_version` | `design-spec/v3` | yes in serialized input | Selects the directional scoring contract without inference. Direct Python construction defaults to v3. |
| `specifications` | nonempty list | yes | Each row contains one inline or contained relative motif and a `seek` or `avoid` direction. Motif IDs must be unique. |
| `length` | integer, 1–10,000 | yes | Exact candidate length in bases. |
| `count` | integer, 1–100,000 | yes | Exact number of distinct candidates to return. |
| `strands` | `forward` or `both` | no | Defaults to `both`. |
| `evaluations` | integer, 1–100,000 | yes | Number of complete candidate evaluations; must be at least `count`. |
| `seed` | nonnegative integer | yes | Seed for deterministic search. |
| `min_distance` | number, 0–1 or null | no | Minimum fraction of differing bases between selected sequences; null and zero are unconstrained. |
| `scoring_semantics` | `relative_pwm_attainment_v2` | no | Version of the model-relative match calculation. |
| `objective_semantics` | `weakest_directional_satisfaction_v1` | no | Version of the minimum-satisfaction objective. |
| `tie_break_semantics` | `leftmost_plus_first_v1` | no | Version of deterministic best-match tie-breaking. |

A two-model request:

```yaml
schema_version: design-spec/v3
specifications:
  - motif: motifs/motif-a.yaml
    direction: seek
  - motif: motifs/motif-b.yaml
    direction: avoid
length: 20
count: 8
strands: both
evaluations: 4096
seed: 7
min_distance: 0.2
```

Each motif is scanned once for its strongest model-relative attainment `a`.
Seek satisfaction is `a`; avoid satisfaction is `1 - a`; `balance_score` is the
minimum satisfaction across the ordered specification list. “Avoid” therefore
weakens the strongest model match across the sequence.

Unknown fields, duplicate YAML/JSON keys and non-finite numbers fail validation.
Use native numbers, such as `length: 20`, rather than quoted numeric strings.

Relative motif references must stay inside the specification directory and may
not traverse symlinks. Inline models follow the [motif-model contract](motif-models.md).
Serialized YAML and JSON must declare `schema_version` for both the design and
every structured motif. An omitted version is rejected rather than silently
interpreted under a historical or directional contract.

`design-spec/v3` rejects `motifs` and `avoiders` rather than assigning them a
new meaning. Hard score ceilings are not part of this contract and are not
silently translated into soft avoidance. Historical artifacts remain tied to
their producing software.

## Combined resource bounds

Validation also caps the work implied by otherwise valid fields:

- at most 1,000,000 candidate–motif rows across specifications;
- at most 10,000,000 selected portfolio bases;
- at most 25,000,000 evaluated bases;
- at most 100,000,000 motif-window base-score operations across specifications,
  or 2,000,000,000 when requesting exactly one candidate;
- at most 10,000,000 pairwise distance base comparisons when distance is positive.

Single-output searches retain at most 256 full evaluation records, which suffices
for exact winner and elite selection. They still retain exact sequence discovery
identities, bounded by the unchanged evaluation and evaluated-base limits.
Multi-output searches retain their complete pool for exact constrained selection.

These bounds prevent unexpectedly large allocations and calculations. Requests outside them
fail before search. A request within them can still fail: the evaluator budget
may produce too few unique candidates, the complete evaluated pool may contain
no distance-feasible subset, or the bounded subset traversal may reach its node
limit before resolving feasibility. Each state has a distinct typed error; none
returns a partial portfolio or weakens the distance rule.
