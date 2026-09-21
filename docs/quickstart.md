---
doc_id: motif-balance-quickstart
title: Run a first design
intent: Design and inspect a small request before using transcription-factor profiles.
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
For inline Python inputs, use the [README examples](../README.md#try-a-design).

## 1. Check the inputs and run the search

The bundled request supplies two toy motifs, a DNA length of two bases and a
request for three sequences. Both motifs prefer different bases at each position,
so neither can receive its ideal sequence without compromising the other.

```bash
# Check the motif files, DNA length and search settings without running a search.
uv run motif-balance design examples/synthetic-pairwise/design.yaml --check

# Evaluate the 16 possible two-base sequences and save three candidates.
uv run motif-balance design examples/synthetic-pairwise/design.yaml \
  --out /tmp/motif-balance-result

# Verify the saved scores and print the sequences and their motif matches.
uv run motif-balance inspect /tmp/motif-balance-result
```

The best balance is **0.5**: the weaker motif match reaches halfway across that
model's possible score range. `AT` is one solution. Here, all 16 sequences are
evaluated, so the result is exact. Larger problems use a limited search budget.

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

Edit a copy of the [request](../examples/synthetic-pairwise/design.yaml):

| Setting | What it changes |
| --- | --- |
| `length` | Available DNA; every motif must fit |
| `direction: seek` or `avoid` | Favor or reduce that motif's strongest match |
| `count` | Number of returned sequences |
| `evaluations` | Number of candidate scores the search may compute |
| `seed` | Random starting choices and search proposals |

Run `--check` before searching the edited request. To select different motif
arrangements, continue with [collections](choose-alternatives.md). For a
three-motif application and recorded search, follow the [example](biological-example.md).
