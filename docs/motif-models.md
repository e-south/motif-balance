---
doc_id: motif-balance-motif-models
title: Motif model reference
intent: Describe accepted motif-model meaning and validation.
audience:
  - API consumers
  - CLI users
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
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

The canonical artifact `motifs.json` records the normalized model content and
content digest used for the run. A filename, database row number, or mutable
external URL is not sufficient identity.

Motif Balance does not fetch, choose, or curate model collections. The caller
supplies a content-bound model and owns the source-selection and conversion
rationale.

## Explicit conversion

JASPAR count matrices are not silently interpreted during `design`. Convert one
under an explicit background and probability-mixture prior weight first:

```bash
motif-balance convert-motif examples/formats/synthetic.jaspar \
  --motif-id regulator_a \
  --background 0.25,0.25,0.25,0.25 \
  --prior-weight 0.1 \
  --out regulator-a.yaml
```

For observed base frequency `p`, background frequency `b`, and declared prior
weight `a`, conversion uses `(p + a*b) / (1 + a)`. This is a probability-mixture
weight, not a count-space pseudocount.

The converted file embeds the original JASPAR digest/name, conversion method,
and prior weight. A file cannot embed its own whole-file digest. When Motif
Balance reads the converted file, the returned model and eventual bundle add
that file's computed digest/name as `canonical_file_digest` and
`canonical_file_name`. Design applies no second hidden correction.
