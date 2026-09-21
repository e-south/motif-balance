---
doc_id: motif-balance-production-pairwise-example
title: Bounded pairwise search example
intent: Exercise the bounded annealed engine through the public CLI and bundle contract.
audience:
  - users
  - maintainers
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-21
doc_type: tutorial
---

# Bounded pairwise search example

Search for eight distinct 12-base sequences satisfying two synthetic `seek`
requirements. The request uses the current directional contract and 4,096
scoring evaluations. Its sequence space is too large for that budget to enumerate,
so it uses bounded annealed search. The constructed models carry no biological
interpretation.

```bash
# Validate the input motifs and search settings without running a search.
uv run motif-balance design examples/production-pairwise/design.yaml --check
# Run the design and save its sequences, matches and scoring inputs.
uv run motif-balance design examples/production-pairwise/design.yaml --out /tmp/motif-pair-result
# Verify the saved result and print its sequences and motif matches.
uv run motif-balance inspect /tmp/motif-pair-result
# Plot the recorded best scores over the search.
uv run motif-balance inspect /tmp/motif-pair-result \
  --format svg --view search --out /tmp/motif-pair-search.svg
```

Run from an installed checkout as described in the [quickstart](../../docs/quickstart.md).
Output paths must not exist. Inspect delivery and search completion separately:
returning eight sequences does not prove that the best possible balance was found.
The search SVG shows recorded best-so-far checkpoints, not a continuous trajectory
or convergence proof.

Use the [four-motif example](../synthetic-multimotif/README.md) to add requirements.
Exact-wheel provenance is a separate advanced operation; follow the
[execution workspace reference](../../docs/reference/execution-receipts.md) when
it is needed, rather than treating attestation as a prerequisite for this example.
