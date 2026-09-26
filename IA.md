---
doc_id: motif-balance-information-architecture
title: Information architecture
intent: Locate the records that define inputs, evaluations and results.
audience: [maintainers, API consumers]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-20
doc_type: reference
---

# Information architecture

A design request defines the motif models and available DNA. An evaluation
records how a sequence matches them. A portfolio selects evaluated sequences,
and a result bundle preserves the inputs, outputs and search record together.
These distinctions keep a change to search or presentation from changing the
meaning of an existing score.

## Inputs and evaluations

`MotifModel` contains position probabilities, an explicit background and source
identity. `MotifSpecification` adds a `seek` or `avoid` direction. `DesignSpec`
combines those requirements with length, output count, strand policy, evaluation
budget, seed and optional sequence separation. See [motif inputs](docs/motif-models.md)
and the [design reference](docs/design-spec.md) for fields and conversion rules.

Scoring returns an immutable `Evaluation` containing the sequence, each motif's
selected strongest match, its score and the overall balance. Coordinates are
zero-based, with the end excluded. Deterministic tie-breaking selects the
leftmost match, then the plus strand. [Methods](docs/methods.md) defines the
log-odds calculation and model-relative scale.

A `Candidate` adds a sequence identifier and rank to an evaluation. A
`Portfolio` contains exactly the requested number of candidates. Search may
propose a new sequence, and selection may choose a different evaluation, but
neither may edit an already scored record.

## Search and selection

Search records the executed method and budget separately from the scoring
problem. The same models, directions, length and strand policy can therefore
be compared under different [search methods](docs/methods.md#explicit-comparison-methods).
Optional [observations](docs/reference/search-observations.md) record selected
search states or evaluated winners without changing the search.

### Selection

Ordinary design returns an exact-size portfolio satisfying its declared
Hamming-distance requirement, or raises a typed error. The manifest records the
best evaluated sequence separately because a distance constraint can exclude
it from the selected set.

[Architecture ranking](docs/choose-alternatives.md) instead groups a supplied
pool by selected-match arrangements and ranks one representative per class.
Its `select_up_to` operation can report a smaller delivered collection; its
`select` operation requires the exact count. Neither enforces sequence separation.

[Constrained portfolio selection](docs/reference/portfolio-selection.md) keeps
the full supplied pool and applies an explicit count, separation and architecture
policy. It distinguishes a feasible set, an optimal set within that pool,
insufficient search of the pool and demonstrated pool infeasibility.

## Sequence variants within a selected arrangement

A [variant library](docs/diversify-sequences.md) starts from one rescored parent.
It contains allowed bases, an exact IUPAC product, every concrete evaluation,
single-substitution diagnostics, and a verification summary. It is separate from
search portfolios and arrangement rankings. Its evaluation count describes only
post-design diversification, without changing the original search budget.

## Saved results and inspection

The result bundle contains `design.json`, `motifs.json`, `candidates.tsv`,
`matches.tsv`, `manifest.json` and a derived `candidates.fasta`. Its manifest
binds inputs, candidates, best observed evaluation, bounded search diagnostics
and file digests. Publication is atomic and refuses an existing destination.
The [public contract](docs/reference/public-contract.md#artifacts) lists current
schema versions.

An [execution workspace](docs/reference/execution-receipts.md) additionally
retains the exact wheel and runtime record. An [inspection](docs/reference/result-inspection.md)
verifies the saved result before producing text, JSON, SVG or HTML. A supplied
candidate can also be rescored and inspected without inventing a search history.
Derived reviews stay outside the bundle and do not change its identity.

## Ownership and navigation

The package owns model interpretation, scoring, search, selection and result
verification. Users choose source models, experimental comparisons and downstream
analyses. Storage systems choose placement and retention. Integrations exchange
explicit inputs and versioned artifacts without importing neighboring source trees.

Use the [documentation hub](docs/README.md) for task instructions, the
[module map](docs/reference/module-map.md) for implementation responsibilities,
and [design contracts](DESIGN.md) for the invariants a change must preserve.
