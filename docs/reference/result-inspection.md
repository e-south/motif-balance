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
last_verified: 2026-08-29
doc_type: reference
journey:
  - inspect
---

# Result inspection

`inspect` verifies one explicit result, replays every published match and
score, and creates one immutable `motif-balance.result-inspection/v4`
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

Inspection supports three user outcomes:

| Outcome | Question |
| --- | --- |
| Design a portfolio | Which ranked sequence alternatives were returned and how do their motif trade-offs differ? |
| Explain a hypothesis | Which supplied motif models, sequence coordinates, strands, and bases produced each score? |
| Reproduce the result | Which exact records, semantics, and identities can be checked again? |

Delivery, search completion, and integrity are independent. A complete
portfolio may have stopped because the evaluation budget was exhausted, while
its artifact bytes may still be externally verified.

The review leads with the portfolio because that is the product output. The
best observed evaluation remains separate from the constrained selected set.
For current bundles the portfolio view reports whether that sequence is a
selected member and at which rank. Older readable bundles may provide only its
recorded hard score when the sequence was never serialized.

The candidate view shows each supplied motif as a fixed-size A/C/G/T glyph
strip whose bar lengths encode the supplied probabilities, maps it to its
selected match, and shows the
supplied sequence 5′→3′ and its coordinate-aligned complement 3′→5′. Forward
matches appear above the primary strand and reverse matches below the
complement. Position-support cells are the observed-base log-likelihood
contributions replayed by scoring; renderers do not rescan a motif or recompute
a score. The linear HTML also provides the exact bounded motif-probability
matrix as an accessible table; the glyph strip is an explanatory encoding, not
a substitute for those numeric values. Shared coordinates are a union of positions covered by more than one
representative window, not evidence of simultaneous occupancy.

Constraint-bearing results display avoider matches on separate lanes with
their ceilings and feasibility state. The portfolio remains ranked by target
`balance_score`; avoider scores are never presented as target objectives or a
weighted penalty.

The portfolio view is a candidate-by-motif matrix in deterministic rank and
canonical motif order. Values remain numeric. Under
`relative_pwm_attainment_v2`, the color scale spans zero to one: the theoretical
raw-LLR extrema over one motif-width word. Neither endpoint is a probability.
After best-window scanning, one remains sequence-attainable by embedding a
score-maximizing word; zero need not be attainable as the best match of a
longer sequence. Explicitly versioned historical results retain their original
scoring interpretation.

The search view is a closed diagnostic in HTML and remains directly exportable
as SVG. It is the running maximum of recorded published hard-minimum scores
against evaluator calls. It is not accepted-state history, literal hill
climbing, chain dynamics, convergence evidence, or a global-optimality claim.
It is omitted when a result has no checkpoints. Current diagnostics retain a
feasible/infeasible status beside every restart-final target score so a target
score from a constraint-violating endpoint cannot be mistaken for an
admissible result.

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
cross-task summaries, scaling, and scientific claim acceptance. The package
does not join result summaries, discover Storage, define a cohort, rank results
across runs, or accept evidence.
