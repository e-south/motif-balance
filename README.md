# ![Motif Balance — balanced motif design](assets/motif-balance-banner.svg)

Design DNA against directional motif specifications. Motif models are usually
used to scan existing DNA for matches. Motif Balance reverses that operation:
given explicit models, seek or avoid directions, and a fixed sequence length,
it searches for sequences that make the weakest model-relative specification
satisfaction as strong as possible. For a seek specification satisfaction is
attainment; for an avoid specification it is one minus attainment. The
best-scoring sequence realization for each motif—its matched word, placement,
strand, and any shared coordinates—emerges from the candidate instead of being
prescribed. The result is an exact-size ranked portfolio with a minimum-distance
constraint for sequence-distinct alternatives. The earlier v2 hard-ceiling
avoider contract remains readable and runnable but is not silently reinterpreted
as directional avoidance.

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
  --format html --out /tmp/motif-balance-review.html
uv run motif-balance inspect /tmp/motif-balance-result \
  --format svg --view candidate --candidate 1 \
  --out /tmp/motif-balance-candidate.svg
```

The sanitized [committed candidate review](examples/synthetic-pairwise/candidate-review.svg)
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
| Understand the method | [Concepts](docs/concepts.md) and [methods](docs/methods.md) |
| Author inputs | [Motif models](docs/motif-models.md) and [DesignSpec](docs/design-spec.md) |
| Score an existing sequence | [Sequence scoring](docs/score-sequences.md) |
| See and read a result | [Inspection and visual review](docs/reference/result-inspection.md) |
| Integrate the package | [Public contract](docs/reference/public-contract.md) |
| Maintain or change it | [Architecture](ARCHITECTURE.md), [engineering contracts](DESIGN.md), and [documentation index](docs/index.md) |

The public Python surface is six nouns—`MotifModel`, `MotifSpecification`,
`DesignSpec`, `MotifMatch`, `Candidate`, and `Portfolio`—and two verbs: `design`
and `score`.
The ordinary CLI has three journeys: `design`, `score`, and `inspect`. The
package fetches no motif database, discovers no result workspace, and assigns
no experiment or publication meaning to an output.

Run `bash ./scripts/agent-verify` for the same package gate used by CI.
