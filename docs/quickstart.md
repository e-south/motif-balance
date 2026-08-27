---
doc_id: motif-balance-quickstart
title: Quickstart
intent: Install the private alpha and produce, verify, and inspect one synthetic result.
audience:
  - new users
  - CLI users
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
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

A private release wheel can instead be installed into a clean environment with
`uv pip install /path/to/motif_balance-0.2.0a2-py3-none-any.whl`. Installation
by package name is not supported during the private alpha.

## Validate, design, and verify

The bundled example uses synthetic motif models:

```bash
uv run motif-balance design examples/synthetic-pairwise/design.yaml --check
uv run motif-balance design examples/synthetic-pairwise/design.yaml \
  --out /tmp/motif-balance-result
uv run motif-balance verify /tmp/motif-balance-result
uv run motif-balance inspect /tmp/motif-balance-result --kind bundle
uv run motif-balance inspect /tmp/motif-balance-result --kind bundle \
  --format html --out /tmp/motif-balance-review.html
```

`--check` resolves motif references, validates resource bounds, compiles the
scoring problem, and reports whether search will be exhaustive or annealed. It
does not search or write a result.

The design command writes a new directory atomically. Choose another path if
the destination already exists. A successful directory contains the canonical
JSON and TSV files plus derived FASTA and HTML views. Always verify it before
reading a table; supply `--expected-bundle-id` when the identity came from an
independent channel.

Open `/tmp/motif-balance-review.html` for the shortest visual walkthrough. It
shows the method sequence, best motif-match coordinates for the top candidate,
within-portfolio motif scores, and best-so-far recorded search checkpoints.
The file is a bounded, script-free projection created after verification. It is
not part of the bundle and cannot change its identity.

## If it fails

The command exits nonzero with a stable error code, field when available, and a
corrective hint. It never relaxes count or distance constraints and never
publishes a partial successful result. Use `--debug` only when diagnosing a
trusted input locally.

Next: author a [motif model](motif-models.md), inspect every
[DesignSpec field](design-spec.md), or [score an existing sequence](score-sequences.md).
