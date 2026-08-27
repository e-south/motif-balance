---
doc_id: motif-balance-result-inspection
title: Result inspection
intent: Explain the one-result review projection, outputs, and interpretation boundary.
audience:
  - users
  - API consumers
  - downstream integrators
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-27
doc_type: reference
journey:
  - inspect
---

# Result inspection

`inspect` verifies one explicit result, replays every published match and
score, and creates one immutable `motif-balance.result-inspection/v2`
projection. Text, JSON, SVG, and HTML all render that same projection. They do
not enter the result bundle or change its identity. Bundle members are read
once into a descriptor-bound byte snapshot; parsing, score replay, and rendering
do not return to mutable paths.

## Choose one output

```bash
# Concise terminal review; bundle is the default source.
motif-balance inspect result/

# Complete typed projection.
motif-balance inspect result/ --format json

# One vector computational review artifact.
motif-balance inspect result/ \
  --format svg --view candidate --candidate 3 \
  --out candidate-003.svg
motif-balance inspect result/ \
  --format svg --view portfolio --out portfolio.svg
motif-balance inspect result/ \
  --format svg --view search --out search.svg

# Optional, self-contained linear review.
motif-balance inspect result/ --format html --out result-review.html
```

HTML and SVG require a new output path outside the inspected result. They are
script-free, self-contained, and use no remote resource. SVG text remains text,
dimensions and `viewBox` are explicit, and semantic group IDs support later
Inkscape composition.

## Reading order

Inspection answers five questions:

| Endpoint | Question |
| --- | --- |
| Delivery | What did the request return? |
| Balance | How does each candidate score across the declared motif models? |
| Realization | Which sequence, coordinates, strand, and bases produced each score? |
| Search record | What best observed hard score was recorded as evaluator calls accumulated? |
| Trust | Which integrity checks and external identities were applied? |

Delivery, search completion, and integrity are independent. A complete
portfolio may have stopped because the evaluation budget was exhausted, while
its artifact bytes may still be externally verified.

The candidate view shows the supplied sequence 5′→3′ and its
coordinate-aligned complement 3′→5′. Forward matches appear above the primary
strand and reverse matches below the complement. Position-support cells are
the observed-base log-likelihood contributions replayed by scoring; renderers
do not rescan a motif or recompute a score. Shared coordinates are a union of
positions covered by more than one representative window, not evidence of
simultaneous occupancy.

The portfolio view is a candidate-by-motif matrix in deterministic rank and
canonical motif order. Values remain numeric. The color scale begins at zero,
preserves values above one, and labels `1.0` as a consensus-relative reference,
not a maximum or probability.

The search view is the running maximum of recorded published hard-minimum
scores against evaluator calls. It is not accepted-state history, literal hill
climbing, chain dynamics, convergence evidence, or a global-optimality claim.
It is omitted when a result has no checkpoints.

## Trust and bounds

A bundle checked against its own manifest is `self_consistent`. Supplying an
independently trusted `--expected-bundle-id` makes it
`externally_verified`. Execution inspection requires `--source execution`; it
is `readable_untrusted` without all four external workspace anchors and
`externally_verified` with them.

Exact distance review stops at the declared base-comparison limit. Large
tables and figures report exact displayed and total counts rather than silently
truncating. Wide SVGs retain a readable minimum width and scroll in HTML on a
narrow screen.

## Boundary

Product inspection explains one result. Research workflows own matched
controls, repeated seeds, exhaustive comparisons, uncertainty, failures,
cross-task summaries, scaling, and scientific claim acceptance. The hidden
`integration catalog` command can join explicit result summaries, but it does
not discover Storage, define a cohort, rank results, or accept evidence.
