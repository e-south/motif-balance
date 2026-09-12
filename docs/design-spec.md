---
doc_id: motif-balance-design-spec
title: Design specification reference
intent: Define directional design-spec/v3, legacy v2, input rules, and resource bounds.
audience:
  - API consumers
  - CLI users
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-08
doc_type: reference
---

# Design specification reference

`DesignSpec` is the complete immutable design request. New directional runs use
`design-spec/v3`. Unknown fields,
duplicate YAML or JSON keys, booleans used as numbers, and non-finite numeric
values fail validation. Numeric fields must use native numbers; quoted values
such as `length: "20"` or `min_distance: "0.2"` are rejected.

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `schema_version` | `design-spec/v3` | yes in serialized input | Selects the directional scoring contract without inference. Direct Python construction still defaults to v2 for source compatibility. |
| `specifications` | nonempty list | yes | Each row contains one inline or contained relative motif and a `seek` or `avoid` direction. Motif IDs must be unique. |
| `length` | integer, 1–10,000 | yes | Exact candidate length in bases. |
| `count` | integer, 1–100,000 | yes | Exact number of distinct candidates to return. |
| `strands` | `forward` or `both` | no | Defaults to `both`. |
| `evaluations` | integer, 1–100,000 | yes | Authoritative evaluator-call budget; must be at least `count`. |
| `seed` | nonnegative integer | yes | Seed for deterministic search. |
| `min_distance` | number, 0–1 or null | no | Minimum normalized Hamming distance; null and zero are unconstrained. |
| `scoring_semantics` | `relative_pwm_attainment_v2` | no | Fixed scoring authority. |
| `objective_semantics` | `weakest_directional_satisfaction_v1` | no | Fixed hard-min public objective over specification satisfaction. |
| `tie_break_semantics` | `leftmost_plus_first_v1` | no | Fixed best-match total order. |

Minimal serialized form:

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
means low attainment under the supplied model, not biological absence or lack
of binding.

Relative motif references must stay inside the specification directory and may
not traverse symlinks. Inline models follow the [motif-model contract](motif-models.md).
Serialized YAML and JSON must declare `schema_version` for both the design and
every structured motif. An omitted version is rejected rather than silently
interpreted under a historical or directional contract.

`design-spec/v3` rejects `motifs` and `avoiders` rather than assigning them a
new meaning. Migrate each positive `motifs` entry to a `seek` specification.
Threshold-based avoiders cannot be translated automatically because a hard
ceiling and a continuous directional max–min objective answer different
questions.

## Hard avoidance constraints

`design-spec/v2` remains the explicit legacy contract for hard upper bounds on
avoider motifs. Its mapping keys must equal each resolved model's `motif_id`:

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
