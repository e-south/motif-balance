---
doc_id: motif-balance-motif-models
title: Motif model reference
intent: Describe accepted motif-model meaning and validation.
audience:
  - API consumers
  - CLI users
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-27
doc_type: reference
---

# Motif model reference

`MotifModel` is the immutable scoring input for one named motif. A model must
carry a stable identifier, a rectangular position-by-base matrix, an explicit
background distribution, and a schema or scoring version. Base order and
strand policy are explicit rather than inferred from a file convention.

Validation rejects unknown fields, duplicate identifiers, missing bases,
non-finite or negative values, inconsistent row widths, non-normalized
probability rows, invalid backgrounds, and a motif longer than the designed
sequence. Reverse-strand evaluation uses the declared DNA reverse-complement
rule; it is not a second independently authored motif.

The canonical artifact `motifs.json` records the validated model content and
content digest used for the run. A filename, database row number, or mutable
external URL is not sufficient identity.

Current `motif-model/v2` identities bind `relative_pwm_attainment_v2`. For each
position the conventional probability consensus chooses the highest supplied
probability, while the score-maximizing reference chooses the highest
log-likelihood ratio against the declared background. These references can
differ. The theoretical minimum and maximum raw LLR over one motif-width word
are the sums of the position-wise minimum and maximum log odds. Both are exact
word-level extrema; after best-window scanning of a longer candidate, the
lower endpoint need not be attainable as that sequence's reported match score.

Structured YAML and JSON motif files must declare `schema_version` explicitly.
This prevents a previously valid unversioned v1 file from being reinterpreted
under v2 scoring. The MEME and explicit JASPAR readers are named format
adapters and therefore construct v2 models explicitly; direct Python
construction also defaults to v2.

Explicit `motif-model/v1` records retain their original
`normalized_llr_v1` digest and null-mean/consensus-relative interpretation so
existing receipts and bundles remain verifiable. They are dispatched as v1;
they are never converted to v2 or emitted as new v2 evidence.

Motif Balance does not fetch, choose, or curate model collections. The caller
supplies a content-bound model and owns the source-selection and conversion
rationale.

## Explicit conversion

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
