---
doc_id: motif-balance-result-inspection
title: Result inspection
intent: Explain verified result review and replayed supplied-candidate views without conflating their provenance.
audience:
  - users
  - API consumers
  - downstream integrators
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-11
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
  --out candidate-003.svg \
  --receipt-out candidate-003.receipt.json
motif-balance inspect result/ \
  --format svg --view portfolio --out portfolio.svg
motif-balance inspect result/ \
  --format svg --view search --out search.svg

# Optional, self-contained linear review.
motif-balance inspect result/ --format html --out result-review.html
```

HTML and SVG require a new output path outside the inspected result. They are
script-free, self-contained, and use no remote resource. All labels, sequence
letters, and numeric text use Arial. Information-logo letters use outlined
Arial Bold letterforms with exact information heights, independent of installed
fonts. Labels and sequence letters remain text; Arial must be installed on the
export host, and publication PDFs should embed it rather than substitute a
different family. Dimensions and `viewBox`
are explicit, and semantic group IDs support later composition.

`--receipt-out` is optional and valid only for a candidate SVG written with
`--out`. Its deterministic sidecar binds the exact emitted SVG digest to the
verified bundle, selected candidate and match-projection digests, source-result
package version, current renderer package version, and a digest of the exact
renderer module bytes. Execution inspection also records the verified release
identity. The sidecar is derived review custody; it does not enter or change the
canonical result bundle.

## Inspect a supplied candidate

An alternative selected from a retained pool need not be a run's winner or a
member of its published portfolio. Use the explicit Python API
`inspect_candidate(candidate: Candidate, spec: DesignSpec) -> CandidateInspection`
from `motif_balance.inspection` to explain that candidate without inventing a
result bundle. The [alternative-selection guide](../choose-alternatives.md#inspect-a-ranked-alternative)
contains a runnable example. This API is unreleased and has no separate CLI.

The operation revalidates both models, checks projection limits, compiles the
supplied scoring context, and evaluates the sequence exactly once. Every stored
evaluation field must match replay, including coordinates, strands, directional
satisfaction, and constraint status. The candidate ID must match its sequence.
It accepts only current directional `design-spec/v3`; no legacy conversion or
path discovery occurs. The original portfolio count does not have to be
attainable, because inspection generates no portfolio.

The immutable `motif-balance.candidate-inspection/v1` contains the scoring
problem, supplied model identities and candidate projection, with
`rank_scope="caller_supplied_order"` and `validation_scope="score_replay"`.
Serialize it with `model_dump_json()`. Pass it to the same
`render_candidate_svg` used for result review. Without an explicit
`candidate_rank`, this route renders the supplied rank; result review still
defaults to portfolio rank 1. A mismatching or non-positive/non-integer selector
fails. The existing Arial duplex/logo contract and rendering limits apply.

Replay establishes consistency under the models provided now, not the origin
of those models, the candidate's original producer, the completeness of its
pool, or the correctness of its rank. A `Candidate` does not carry an original
model digest. Keep source receipts with the caller; JSON schema validation is
not independent replay. This projection has no run, bundle, search or integrity
state and cannot receive a bundle-custody SVG receipt. Text, portfolio, search
and HTML result views still require `ResultInspection`.

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

The current candidate visual contract is `motif-balance.candidate-duplex/v2`.
There is one candidate view, not a legacy/current display switch. It consumes
verified result inspection or replayed supplied-candidate inspection; it does not
depend on a study directory, another renderer, or a particular motif source.

For uniform-background models, the candidate view shows each supplied motif as
a coordinate-aligned 0–2 bit information logo over its selected match and shows
the supplied sequence 5′→3′ with its coordinate-aligned complement 3′→5′.
The observed base in each logo column uses the motif's categorical color;
unobserved alternatives remain gray. Each selected window has a solid motif-colored
fill and white bases on the same coordinate grid and at the same font size as
the duplex. Forward logos and matches appear above the
primary strand and reverse logos and matches below the complement. Limiting
motifs use an explicit bracket and label. Hard-ceiling avoiders use a dashed
outline and display their ceiling, so neither state depends on color alone.

Exact observed-base signed log-likelihood contributions remain in the JSON and
HTML inspection, not as a second numeric grid in the molecular SVG. Each logo
column has information height `2 − H(p)` bits; its base letters have heights
`p(base) × (2 − H(p))`. Uniform columns have zero height, without artificial
minimum-size letters. These heights are not LLRs or binding probabilities.
Renderers use the projected
matrix, coordinates, strand, and support records; they do not rescan a motif or
recompute a score. Candidate SVG export fails clearly for a nonuniform scoring
background because a 0–2 bit logo would imply the uniform-background convention;
text and JSON inspection remain available. The linear HTML also provides the
exact bounded motif-probability matrix as an accessible table; the logo is an
explanatory encoding, not a substitute for those numeric values. Shared
coordinates are a union of positions covered by more than one representative
window, not evidence of simultaneous occupancy. More than 32 selected matches
fails explicitly instead of silently exporting an incomplete molecular view;
use JSON for the complete records. No lane is dropped to fit a page.

For directional results, every model carries a seek/avoid direction and a
satisfaction. The weakest satisfaction limits balance; avoid satisfaction is
one minus the strongest scanned attainment. A strong unwanted match therefore
reduces balance rather than disappearing from the review.

Explicit hard-ceiling results display avoider matches on separate lanes with
their ceilings and feasibility state. The portfolio remains ranked by target
`balance_score`; avoider scores are never presented as target objectives or a
weighted penalty.

The portfolio view is a candidate-by-motif matrix in deterministic rank and
canonical motif order. Values remain numeric. Under
`relative_pwm_attainment_v2`, the color scale spans zero to one: the theoretical
raw-LLR extrema over one motif-width word. Neither endpoint is a probability.
After retaining the best score across multiple placements or orientations, one
remains sequence-attainable by embedding a score-maximizing word; zero need not
be attainable as the sequence's reported best match. Explicitly versioned
historical results retain their original scoring interpretation.

The search view is a closed diagnostic in HTML and remains directly exportable
as SVG. It is the running maximum of recorded published hard-minimum scores
against evaluator calls. It is not accepted-state history, literal hill
climbing, chain dynamics, convergence evidence, or a global-optimality claim.
Held steps preserve the recorded checkpoint values; improvement times between
checkpoints are unknown. If the display must omit score changes, it uses
unconnected sampled markers and discloses displayed and total counts.
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
does not join result summaries, discover storage, define a cohort, rank results
across runs, or accept evidence.
