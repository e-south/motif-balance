# ![Motif Balance — balanced motif design](assets/motif-balance-banner.svg)

Motif Balance is a deterministic inverse-design package for fixed-length DNA
sequences evaluated against explicit motif models. Under
`normalized_llr_v1`, it maximizes the weakest normalized motif score and
returns an exact number of distinct, fully re-evaluated candidates. An optional
minimum-distance constraint can make that portfolio sequence-diverse.

This repository is a public prerelease and is not approved for PyPI publication.
Outputs are model-relative computational results; they do not establish
binding, expression, synthesis readiness, biological function, or global
optimality.

## First verified design

```bash
uv sync --locked --group dev
uv run motif-balance design examples/synthetic-pairwise/design.yaml --check
uv run motif-balance design examples/synthetic-pairwise/design.yaml \
  --out /tmp/motif-balance-result
uv run motif-balance verify /tmp/motif-balance-result
uv run motif-balance inspect /tmp/motif-balance-result --kind bundle
uv run motif-balance inspect /tmp/motif-balance-result --kind bundle \
  --format html --out /tmp/motif-balance-review.html
```

The result contains five canonical files—`design.json`, `motifs.json`,
`candidates.tsv`, `matches.tsv`, and `manifest.json`—plus verified FASTA and
HTML views. Publication is atomic and refuses an existing destination.
The external review HTML is an on-demand, script-free visual walkthrough; it
does not change the verified bundle or its identity.

## Choose a route

| Goal | Route |
| --- | --- |
| Install, design, and verify | [Quickstart](docs/quickstart.md) |
| Understand the method | [Concepts](docs/concepts.md) and [methods](docs/methods.md) |
| Author inputs | [Motif models](docs/motif-models.md) and [DesignSpec](docs/design-spec.md) |
| Score an existing sequence | [Sequence scoring](docs/score-sequences.md) |
| See and read a result | [Inspection and visual review](docs/reference/result-inspection.md) |
| Integrate the package | [Public contract](docs/reference/public-contract.md) |
| Maintain or change it | [Architecture](ARCHITECTURE.md), [engineering contracts](DESIGN.md), and [documentation index](docs/index.md) |

Use only the `motif_balance` facade and the `motif-balance` command. Scientific
inputs belong in an immutable `DesignSpec`; operational flags select validation
or output behavior. The package fetches no motif database, discovers no result
workspace, and assigns no experiment or publication meaning to an output.

Run `bash ./scripts/agent-verify` for the same package gate used by CI.
