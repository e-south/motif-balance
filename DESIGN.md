# Design contracts

Changing search effort or presentation must not change the score assigned to a
fixed DNA sequence. These invariants govern implementation changes; the linked
references own formulas, parameters, and file formats.

## Models and scoring

- Public models are strict and immutable. Unknown fields, non-finite values, and
  quoted numeric strings fail validation.
- Motif preparation is explicit and records its source, prior, and background.
  Compilation never applies a hidden second correction. See [motif
  inputs](docs/motif-models.md) and [conversion](docs/reference/motif-conversion.md).
- DNA uses uppercase A/C/G/T. Coordinates are zero-based and end-exclusive. Each
  requirement contributes one best match using its strand policy and the
  deterministic leftmost, plus-strand-first tie rule.
- Seek satisfaction is normalized match attainment; avoid satisfaction is one
  minus attainment. Reported balance is their hard minimum. Smooth guidance
  scores remain internal to search. [Methods](docs/methods.md) defines both.
- Normalization uses extrema over one motif-width word. Scanning preserves the
  upper endpoint but can make the lower endpoint unattainable as a sequence's
  best match. See [interpretation](docs/interpreting-results.md).
- Scoring produces an immutable evaluation. Search, selection, and rendering
  cannot edit its sequence, sites, or scores afterward.

## Search and selection

A request fixes DNA length, count, seed, strand policy, and evaluation allowance.
[Resource bounds](docs/design-spec.md#combined-resource-bounds) are checked before
allocation or search. Bounded methods execute the requested algorithm at every
length; exhaustive enumeration requires an explicit request.

A method or initialization change alters the run identity, not the scoring
problem. Observations must leave the random stream, evaluated candidates, and
selected portfolio unchanged. Every evaluator call counts, including repeats
and rejected proposals. The best observed evaluation remains separate from the
selected portfolio. Only complete enumeration establishes a whole-space optimum.

Ordinary design returns exactly the requested count under the declared sequence
separation or fails. [Arrangement ranking](docs/choose-alternatives.md) groups
supplied sequences and supports explicit partial delivery through `select_up_to`.
[Constrained selection](docs/reference/portfolio-selection.md) retains the full
pool and distinguishes a feasible witness, pool optimality, unresolved work,
and demonstrated infeasibility. None silently relaxes a requested constraint.

Candidate sequences and identifiers are unique. Ties use stable total orderings
independent of scheduling, mapping order, locale, and host.

## Expansion after design

[Explicit expansion](docs/expand-sequences.md) traverses qualifying one-base
neighbors in deterministic breadth-first order. It retains every qualifying
evaluation within the work and output limits, using the original parent's
selected sites and the common balance floor. An exhausted frontier does not
establish global sequence-space exhaustion.

[Degenerate libraries](docs/diversify-sequences.md) instead return a complete
Cartesian product whose every member passes. Absolute-floor and parent-relative
loss modes are mutually exclusive. The fixed-site additive precheck can reject
an expansion, but complete scans still establish each accepted member's scores
and selected sites. Collections validate all parents and aggregate limits before
construction. Both operations include the parent and freeze uncovered positions
by default; neither changes search or arrangement definitions.

## Results and changes

Canonical artifacts bind inputs, versions, seeds, budgets, and content digests.
[Verification](RELIABILITY.md) replays their scoring and decisions before
publication or inspection. Derived views do not alter the bundle. Supplied-
candidate inspection verifies its scores and sites without asserting a search
origin or portfolio membership.

The [public contract](docs/reference/public-contract.md#artifacts) lists supported
schemas. Historical records retain their producing-version requirements.
Malformed input, infeasible requests, exhausted bounded selection, and corrupted
artifacts have distinct failures rather than partial successful results.

Add a failing contract test before changing behavior. Changes to score meaning,
public schemas, or search behavior need compatibility documentation and negative
cases. Keep refactors separate from numerical changes.
