# ![Motif Balance — balanced motif design](assets/motif-balance-banner.svg)

Design fixed-length DNA to satisfy several motif requirements, then inspect
which requirement limits each sequence. Supply motif models with `seek` or
`avoid` directions; Motif Balance searches for sequences that improve the
weakest requirement. Matching words, positions, strands, and overlap emerge
from the sequence rather than being prescribed.

The result is an exact-size ranked portfolio, optionally constrained to contain
sequence-distinct alternatives. Each candidate retains its sequence, strongest
motif matches, directional satisfactions, and limiting requirement. One verified
result supports terminal review, machine-readable tables, and static SVG figures.

This repository is a public prerelease and is not approved for PyPI publication.
The `0.5` alpha supports CPython 3.12–3.14 on Linux and macOS. Linux is the
hosted CI authority and macOS is exercised locally. Other operating systems are
not yet supported.
Outputs are inspectable sequence hypotheses under the supplied models.
Exhaustive runs establish an optimum only when the admitted sequence space is
fully enumerated; larger searches report the best result observed under the
declared evaluator-call budget. Shared motif-window coordinates do not
establish simultaneous occupancy or co-binding, and outputs do not establish
binding, expression, synthesis readiness, or biological function.

## First design

```bash
uv sync --locked --group dev
uv run motif-balance design examples/synthetic-pairwise/design.yaml --check
uv run motif-balance design examples/synthetic-pairwise/design.yaml \
  --out /tmp/motif-balance-result
uv run motif-balance inspect /tmp/motif-balance-result
uv run motif-balance inspect /tmp/motif-balance-result \
  --format svg --view candidate --candidate 1 \
  --out /tmp/motif-balance-candidate.svg
```

This synthetic example uses the current directional design contract and complete
enumeration of 16 sequences. The [committed candidate review](examples/synthetic-pairwise/candidate-review.svg)
connects each supplied motif model to its selected strand-aware match, shared
sequence coordinates, and base-level score support without requiring a browser
application.

The immutable bundle contains five canonical files—`design.json`,
`motifs.json`, `candidates.tsv`, `matches.tsv`, and `manifest.json`—plus a
derived FASTA export. `inspect` verifies bytes and score replay before it
creates text, JSON, SVG, or optional script-free HTML. Review files remain
outside the bundle and do not change its identity.

## Choose a route

| Goal | Route |
| --- | --- |
| Install, design, and inspect | [Quickstart](docs/quickstart.md) |
| Design from Python | [Self-contained Python tutorial](docs/python-api.md) |
| Assess a pair before search | [Length-aware pair assessment](docs/pair-assessment.md) (unreleased API and CLI) |
| Understand the method | [Concepts](docs/concepts.md) and [methods](docs/methods.md) |
| Seek or avoid a match | [Directional inputs](docs/design-spec.md); hard thresholds are a separate explicit contract |
| Author inputs | [Motif models](docs/motif-models.md) and [DesignSpec](docs/design-spec.md) |
| Score an existing sequence | [Sequence scoring](docs/score-sequences.md) |
| See and read a result | [Inspection and visual review](docs/reference/result-inspection.md) |
| Choose different arrangements from an explicit sequence pool | [Alternative selection](docs/choose-alternatives.md) (unreleased Python API) |
| Integrate the package | [Public contract](docs/reference/public-contract.md) |
| Maintain or change it | [Architecture](ARCHITECTURE.md), [engineering contracts](DESIGN.md), and [documentation index](docs/index.md) |

The top-level Python facade is six nouns—`MotifModel`, `MotifSpecification`,
`DesignSpec`, `MotifMatch`, `Candidate`, and `Portfolio`—and two verbs: `design`
and `score`. Pair assessment and architecture selection are explicit submodule
APIs, reached through the task guides above; they do not expand that facade.
The ordinary CLI has four journeys: `assess`, `design`, `score`, and `inspect`. The
package fetches no motif database, discovers no result workspace, and assigns
no experiment or publication meaning to an output. Cross-request compression,
quality-matched diversity, predictive validation, and cohort figures belong
to callers, not the product's single-request interface.

Run `bash ./scripts/agent-verify` for the same package gate used by CI.
