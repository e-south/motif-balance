---
doc_id: motif-balance-quickstart
title: Run a first design
intent: Design and inspect a small request before using biological profiles.
audience: [users]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-20
doc_type: tutorial
journey: [install, design, verify]
---

# Run a first design

[Install the package](installation.md), then use this small example to check
the complete design-to-inspection workflow. It uses two-position synthetic
models so the result is easy to verify. For a transcription-factor application,
continue with the [Dorsal, Twist and Zelda example](biological-example.md).

## Design a sequence set

The commands below run from a source checkout. With a wheel installation, copy
the complete [example directory](../examples/synthetic-pairwise/README.md),
including its `motifs/` folder, and use `motif-balance` in place of
`uv run motif-balance`.

```bash
uv run motif-balance design examples/synthetic-pairwise/design.yaml --check
uv run motif-balance design examples/synthetic-pairwise/design.yaml \
  --out /tmp/motif-balance-result
uv run motif-balance inspect /tmp/motif-balance-result
```

`--check` validates the motifs, length, requested count and computational limits
without starting a search. This example is small enough to evaluate all 16
possible sequences. The terminal summary reports the best evaluated balance
and the selected candidate set.

Choose a new destination before repeating the command. Design never replaces
an existing result. The directory contains the input models and request,
candidate and match tables, FASTA sequences and a manifest recording the search.
Keep the directory intact; `inspect` checks those files and replays their scores.

## Inspect matches and export a figure

```bash
uv run motif-balance inspect /tmp/motif-balance-result \
  --format svg --view candidate --out /tmp/motif-balance-candidate.svg
uv run motif-balance inspect /tmp/motif-balance-result \
  --format html --out /tmp/motif-balance-review.html
```

Open the SVG to see the duplex, selected motif windows and aligned information
logos. The HTML combines candidate, portfolio and recorded-search views in one
local file. These exports stay outside the result directory and do not alter it.

## Adapt the request

Supply your [motif models](motif-models.md), then edit the
[design specification](design-spec.md):

- `length` sets the available DNA and must fit every model.
- `seek` favors a strong motif match; `avoid` favors a weak strongest unwanted match.
- `count` requests the number of sequences to return.
- `min_distance` optionally requires a fraction of differing sequence positions.
- `evaluations` and `seed` set search effort and reproducibility.

Run `--check` after changing inputs. More evaluations may recover better
candidates, but do not guarantee a stronger score or more distinct arrangements.
Use [collections](choose-alternatives.md) when the desired alternatives differ
in motif arrangement rather than only sequence distance.

## Understand a failure

An invalid request exits nonzero and identifies the offending field or
condition. A run can also fail to find the requested number of sufficiently
separated sequences. It does not silently return fewer candidates or relax
the distance rule. Use a new output path when a destination already exists;
use `--debug` for a traceback when diagnosing a trusted input locally.

Next: [biological example](biological-example.md), [Python tutorial](python-api.md),
[score existing DNA](score-sequences.md), or [interpret the result](interpreting-results.md).
