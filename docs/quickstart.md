---
doc_id: motif-balance-quickstart
title: Run a first design
intent: Design and inspect DNA using the ArgR and Cra transcription-factor profiles.
audience: [users]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-21
doc_type: tutorial
journey: [install, design, verify]
---

# Run a first design

Fit two motif preferences into one short sequence, save the result, then inspect
where each motif matches. Start from the [installed source checkout](installation.md#install-from-source).
For Python inputs, use the [README examples](../README.md#try-a-design).

## 1. Check the inputs and run the search

The bundled request fits the ArgR and Cra motifs into 32 base pairs and asks
for four sequences. The motifs span 25 and 14 positions, so their best matches
must share some positions. Their [source and preparation](../examples/argr-cra/README.md)
are recorded with the inputs.

```bash
# Check the motif files, DNA length and search settings without running a search.
uv run motif-balance design examples/argr-cra/design.yaml --check

# Evaluate up to 4,096 candidates and save four sequences.
uv run motif-balance design examples/argr-cra/design.yaml \
  --out /tmp/motif-balance-result

# Verify the saved scores and print the sequences and their motif matches.
uv run motif-balance inspect /tmp/motif-balance-result
```

The best balance is approximately **0.880**: the weaker of the two best motif
matches, scored relative to its model's possible range. This is a bounded search
through the 32-base sequence space.

Use a new output directory when rerunning. The saved directory contains the
request, input motifs, sequences, match tables and search record.

## 2. View the sequence and its motif matches

```bash
# Draw the best candidate as double-stranded DNA with aligned motif logos.
uv run motif-balance inspect /tmp/motif-balance-result \
  --format svg --view candidate --out /tmp/motif-balance-candidate.svg

# Create a browser view of the candidate set and its scores.
uv run motif-balance inspect /tmp/motif-balance-result \
  --format html --out /tmp/motif-balance-review.html
```

Open the SVG in an image viewer or the HTML in a browser. The filled windows
show the selected best match to each motif; the logos show its base preferences.
These exports leave the saved result unchanged.

## 3. Change the design question

Edit a copy of the [request](../examples/argr-cra/design.yaml):

| Setting | What it changes |
| --- | --- |
| `length` | Available DNA; every motif must fit |
| `direction: seek` or `avoid` | Favor or reduce that motif's strongest match |
| `count` | Number of returned sequences |
| `evaluations` | Number of candidate scores the search may compute |
| `seed` | Random starting choices and search proposals |

Run `--check` before searching the edited request. To select different motif
arrangements, continue with [collections](choose-alternatives.md). For a
twelve-model application and recorded search, follow the [example](biological-example.md).

## Compare search methods

Keep the same request, seed and evaluation allowance while changing the method:

```bash
for method in annealed greedy random; do
  uv run motif-balance design examples/argr-cra/design.yaml \
    --method "$method" --out "/tmp/motif-balance-$method"
done
```

Use new output directories. Annealed is the default; greedy and annealed
enumerate when the complete sequence space fits the allowance, while random
always samples with replacement. The output reports the actual engine.
Equal evaluation allowances do not imply equal elapsed time. See the
[Python comparison](python-api.md#compare-search-methods) and
[method definitions](methods.md#explicit-comparison-methods).
