---
doc_id: motif-balance-motif-conversion
title: Motif conversion records
intent: Record how counts or source probabilities become scoring inputs.
audience: [API consumers]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-21
doc_type: reference
---

# Motif conversion records

Motif Balance recognizes four named conversion methods across two schema
versions:

| Method | Use |
| --- | --- |
| `count_matrix_sqrt_n_background_prior_v1` | `motif-conversion/v2`; convert a count matrix with a position-specific background-weighted prior of `sqrt(N_i)`. New JASPAR preparation uses this method. |
| `jaspar_counts_to_probabilities_v1` | Historical alpha conversion using a caller-supplied probability-mixture weight; readable but no longer emitted. |
| `probability_matrix_prior_mixture_v1` | Record an upstream, data-owner conversion of a probability matrix containing zero values. |
| `probability_matrix_target_background_v1` | `motif-conversion/v2`; record the source-declared background separately from an explicit target background used for regularization and scoring. |

JASPAR count matrices are not silently interpreted during `design`. Convert one
under an explicit background first. For observed count `n[i,b]`, column count
`N[i]`, and background `q[b]`, the conversion uses the position-specific prior
`alpha[i] = sqrt(N[i])` and
`(n[i,b] + alpha[i]*q[b]) / (N[i] + alpha[i])`:

```bash
# Convert source counts into a probability model with an explicit background.
motif-balance motif prepare examples/formats/synthetic.jaspar \
  --motif-id regulator_a \
  --background 0.25,0.25,0.25,0.25 \
  --out regulator-a.yaml
```

Probability matrices have no effective sample size. Their separate declared
conversion uses `(p + a*q) / (1 + a)` and requires a positive prior weight and
an explicit source motif identity. Motif Balance validates that provenance
when reading a canonical motif model; it does not fetch the source or choose
the probability-matrix prior. When a data owner converts a source matrix under
an explicit target background, the v2 conversion also records the source
background, target background, and `explicit_target_background_v1` policy.
Motif Balance requires the model's scoring background to equal that declared
target; disagreement fails before compilation or scoring.

A converted file embeds the original source digest/name and conversion method.
Count conversion also embeds the observed count, prior mass, and denominator
for every position; probability conversion embeds its declared prior weight. A
file cannot embed its own whole-file digest. When Motif Balance reads the
converted file, the returned model and eventual bundle add that file's computed
digest/name as `canonical_file_digest` and `canonical_file_name`. Design applies
no second hidden correction.

Return to [motif inputs](../motif-models.md).
