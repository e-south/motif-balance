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

Motif Balance does not fetch or curate biological model collections. A data
producer exports the explicit model, and the study records why that model was
chosen.
