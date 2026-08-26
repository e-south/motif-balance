# Motif Balance

Motif Balance is a standalone, deterministic inverse-design package for fixed-length DNA
sequences evaluated against explicit motif models. Version 1 reports the weakest normalized
motif score and returns an exact number of unique, fully re-evaluated candidates. When a
minimum distance is declared, selection enforces it without relaxation.

This prerelease repository is private and not approved for PyPI publication. It makes
computational design and scoring claims only; it does not establish binding, expression,
promoter function, regulatory grammar, synthesis readiness, or global optimality.

Install the locked development environment and inspect the command surface:

```bash
uv sync --locked --group dev
uv run motif-balance --help
```

The ordinary interface is one strict specification and one operation:

```bash
uv run motif-balance design examples/synthetic-pairwise/design.yaml \
  --out /tmp/motif-balance-example
```

```python
from motif_balance import DesignSpec, MotifModel, design

spec = DesignSpec(
    motifs=(
        MotifModel(
            motif_id="left",
            probabilities=((0.7, 0.1, 0.1, 0.1),),
            background=(0.25, 0.25, 0.25, 0.25),
        ),
    ),
    length=4,
    count=2,
    strands="both",
    evaluations=256,
    seed=7,
    min_distance=0.25,
)
portfolio = design(spec)
portfolio.write("result")
```

A successful result contains five canonical files—`design.json`, `motifs.json`,
`candidates.tsv`, `matches.tsv`, and `manifest.json`—plus derived FASTA and HTML views. Verify
the bundle before consuming any table:

```bash
uv run motif-balance verify result
```

Evidence-producing runs should use `motif-balance execute` with the exact wheel and
producer revision. That command creates an atomic, independently verifiable execution
workspace; see the execution-workspace reference linked from the documentation index.

See [the documentation route](docs/index.md) for motif conversion, score interpretation,
artifact verification, [information architecture](IA.md), limitations, and the
manuscript-evidence boundary. Run
`bash ./scripts/agent-verify` for the same package gate used by CI.
