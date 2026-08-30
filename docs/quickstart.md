---
doc_id: motif-balance-quickstart
title: Quickstart
intent: Install the prerelease and produce, verify, and inspect one synthetic result.
audience:
  - new users
  - CLI users
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-28
doc_type: tutorial
journey:
  - install
  - design
  - verify
---

# Quickstart

## Install

From a source checkout, install the locked development environment:

```bash
uv sync --locked --group dev
uv run motif-balance --help
```

A released wheel can instead be installed into a clean environment with
`uv pip install /path/to/motif_balance-0.4.0a4-py3-none-any.whl`. Installation
by package name is not supported during the prerelease.

## Validate, design, and inspect

The bundled example uses synthetic motif models:

```bash
uv run motif-balance design examples/synthetic-pairwise/design.yaml --check
uv run motif-balance design examples/synthetic-pairwise/design.yaml \
  --out /tmp/motif-balance-result
uv run motif-balance inspect /tmp/motif-balance-result
uv run motif-balance inspect /tmp/motif-balance-result \
  --format html --out /tmp/motif-balance-review.html
uv run motif-balance inspect /tmp/motif-balance-result \
  --format svg --view candidate --out /tmp/motif-balance-candidate.svg
```

`--check` resolves motif references, validates resource bounds, compiles the
scoring problem, and reports whether search will be exhaustive or annealed. It
does not search or write a result.

The terminal result distinguishes the highest-scoring evaluated sequence from
the exact selected portfolio. Under a distance constraint the best observed
sequence can be excluded from the selected set; the current manifest retains
both facts without relaxing the constraint.

The design command writes a new directory atomically. Choose another path if
the destination already exists. A successful directory contains the five
canonical JSON and TSV files plus a derived FASTA member. `inspect` verifies
the bundle before reading it; supply `--expected-bundle-id` when the identity
came from an independent channel.

Open `/tmp/motif-balance-review.html` for the optional linear walkthrough. It
separates delivery, search completion, and integrity; then shows exact duplex
placement, the candidate-by-motif balance matrix, and the recorded running
maximum of the hard score. The SVG is the smaller vector review artifact.
Both are bounded, script-free projections outside the bundle.

## If it fails

The command exits nonzero with a stable error code, field when available, and a
corrective hint. It never relaxes count or distance constraints and never
publishes a partial successful result. Use `--debug` only when diagnosing a
trusted input locally.

Next: author a [motif model](motif-models.md), inspect every
[DesignSpec field](design-spec.md), or [score an existing sequence](score-sequences.md).
