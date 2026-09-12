---
doc_id: motif-balance-quickstart
title: Quickstart
intent: Install the prerelease and produce, verify, and inspect one synthetic result.
audience:
  - new users
  - CLI users
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-08
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

For a supplied release wheel, create an environment in your own working directory:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python /path/to/motif_balance-0.5.0a2-py3-none-any.whl
.venv/bin/motif-balance --help
```

Replace the wheel path with your actual file. Installation by package name is
not supported during the prerelease. The wheel does not install the repository's
`examples/` directory: use the [self-contained Python tutorial](python-api.md),
or copy the complete [synthetic example directory](../examples/synthetic-pairwise/README.md)
including its `motifs/` inputs and run `.venv/bin/motif-balance` against the
copied `design.yaml`. The commands below assume the source checkout.

## Validate, design, and inspect

The bundled example uses two synthetic `seek` requirements in the current
directional schema. It is small enough to evaluate all 16 possible sequences:

```bash
uv run motif-balance design examples/synthetic-pairwise/design.yaml --check
uv run motif-balance design examples/synthetic-pairwise/design.yaml \
  --out /tmp/motif-balance-result
uv run motif-balance inspect /tmp/motif-balance-result
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

The design command rejects an existing destination before searching, then writes
a new directory atomically with a second no-overwrite check. Choose another path
if the destination already exists. A successful directory contains the five
canonical JSON and TSV files plus a derived FASTA member. `inspect` verifies
the bundle before reading it; supply `--expected-bundle-id` when the identity
came from an independent channel.

Open the SVG to inspect the sequence, selected motif placements, and limiting
requirement. For a complete optional walkthrough:

```bash
uv run motif-balance inspect /tmp/motif-balance-result \
  --format html --out /tmp/motif-balance-review.html
```

The HTML combines candidate, portfolio, and recorded-search views. Neither
format changes the result bundle or requires a running browser application.

## Adapt the request

- Set each specification to `seek` or `avoid`; the latter weakens its strongest
  scanned match, not just one selected window.
- Change `length` to change the available DNA. It must accommodate every motif.
- Set `count` and optional `min_distance` to select sequence-distinct designs.
- Set `evaluations` and `seed` explicitly. A larger budget is another run,
  not a guarantee of convergence or more alternatives.

Re-run `--check` after editing. See the [design reference](design-spec.md) for
the exact fields and limits; the product does not select experimental cohorts
or infer scientific conclusions from repeated requests.

For bounded search and more requirements, continue with the
[pairwise search example](../examples/production-pairwise/README.md) or the
[four-motif example](../examples/synthetic-multimotif/README.md). Both use the
same current contract and ordinary commands; neither requires release attestation.

## If it fails

The command exits nonzero. Input and result failures report a stable domain
code; command-line usage errors report the invalid argument. Fields and
corrective hints are supplied where available. It never relaxes count or distance constraints and never
publishes a partial successful result. Use `--debug` only when diagnosing a
trusted input locally.

Next: author a [motif model](motif-models.md), inspect every
[DesignSpec field](design-spec.md), or [score an existing sequence](score-sequences.md).
