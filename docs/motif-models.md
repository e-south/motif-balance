---
doc_id: motif-balance-motif-models
title: Supply motif models
intent: Prepare explicit probability models from count or probability matrices.
audience: [users]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-20
doc_type: how-to
---

# Supply motif models

Start with transcription-factor motif profiles or other DNA preference models
appropriate to your question. Motif Balance accepts position probabilities
and an explicit background distribution. It converts these to log-odds weights
when scoring; it does not fetch a database or choose profiles for you.

Keep the source identifier and version with each profile. If you compare
models, record how you prepared their probabilities and why you chose the
scoring background. A shared representation makes the calculation consistent;
it does not erase differences in the experiments used to estimate the models.

## Prepare a JASPAR count matrix

Download one profile in JASPAR count format, preserving its accession and
version. From the repository checkout, this small format example demonstrates
conversion with an equal-frequency A/C/G/T background:

```bash
motif-balance motif prepare examples/formats/synthetic.jaspar \
  --motif-id regulator_a \
  --background 0.25,0.25,0.25,0.25 \
  --out regulator-a.yaml
```

Replace the source path and ID with your chosen profile. For each position,
the converter adds a background-weighted pseudocount mass equal to the square
root of the observed count, then divides by the resulting total. This makes
all base probabilities positive and avoids undefined log odds for zero counts.
The output records the source and conversion parameters. The precise formula
and metadata are in [conversion records](reference/motif-conversion.md).

Use the [Dorsal, Twist and Zelda example](biological-example.md) to follow this process
with attributed biological profiles.

## Read a MEME probability profile

Use the MEME record identifier explicitly when reading a file that contains
more than one motif:

```python
from pathlib import Path
from motif_balance.formats import read_motif

model = read_motif(Path("profiles.meme"), motif_id="selected_record_id")
with Path("selected-model.json").open("x") as output:
    output.write(model.model_dump_json(indent=2) + "\n")
```

Replace the filename and identifier with your source. This reader expects an
A/C/G/T probability matrix and declared background frequencies. It does not
run MEME or apply smoothing. If the source contains zero probabilities, prepare
positive probabilities explicitly and retain the conversion record rather than
silently replacing zero values. Probability matrices have no known sample size;
their smoothing parameters are distinct from count pseudocounts.

## Author or inspect a canonical model

A YAML or JSON model declares its schema and stable ID. Each matrix row is one
motif position; columns are always A, C, G, T:

```yaml
schema_version: motif-model/v2
motif_id: example_ac
probabilities:
  - [0.7, 0.1, 0.1, 0.1]
  - [0.1, 0.7, 0.1, 0.1]
background: [0.25, 0.25, 0.25, 0.25]
```

This two-position example explains the format. Use experimentally derived
profiles for your own design question. All entries and background probabilities
must be finite and positive, and each row and the background must sum to one.
Unknown fields, malformed matrices and unsupported versions are rejected.

## Add models to a design

Keep motif files in the design directory or a subdirectory and reference them
from `specifications`:

```yaml
specifications:
  - motif: motifs/desired.yaml
    direction: seek
  - motif: motifs/unwanted.yaml
    direction: avoid
```

The [complete design reference](design-spec.md) supplies the other required
fields. Motif references must remain within the design directory and cannot
traverse symlinks. The chosen DNA length must fit every motif. Both-strand
scoring derives reverse complements from each model; do not supply a second
model just to request reverse-strand scanning.

The saved `motifs.json` retains validated model content and its digest, so
later inspection uses the exact probabilities used during design.
