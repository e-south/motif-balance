---
doc_id: motif-balance-synthetic-multimotif-example
title: Annealed four-motif example
intent: Exercise one multi-motif design through the same public product contract.
audience:
  - users
  - maintainers
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-08
doc_type: tutorial
---

# Annealed four-motif example

Search for four distinct eight-base sequences under four synthetic `seek`
requirements. The current directional contract scores the weakest of all four
satisfactions, using the same design and inspection operations as the pairwise
example. The 2,048-evaluation budget uses bounded annealed search, not complete
enumeration. The constructed models carry no biological interpretation.

```bash
uv run motif-balance design examples/synthetic-multimotif/design.yaml --check
uv run motif-balance design examples/synthetic-multimotif/design.yaml --out /tmp/motif-four-result
uv run motif-balance inspect /tmp/motif-four-result
uv run motif-balance inspect /tmp/motif-four-result \
  --format svg --view portfolio --out /tmp/motif-four-portfolio.svg
```

Run from an installed checkout as described in the [quickstart](../../docs/quickstart.md).
Output paths must not exist. The portfolio view makes the limiting requirement
visible for each candidate. Adding models changes the design problem; this
example alone does not establish how difficulty scales with motif count.

Change a direction to `avoid` only when that model's strongest sequence-wide
match should be weakened. This changes the objective, not just a display label;
it does not impose a hard exclusion threshold. See [directional scoring](../../docs/concepts.md#one-objective-for-desired-and-unwanted-matches).
