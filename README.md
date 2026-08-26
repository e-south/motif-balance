# Motif Balance

Motif Balance is a standalone, deterministic inverse-design package for fixed-length DNA
sequences evaluated against explicit motif models. Version 1 reports the weakest normalized
motif score and returns an exact number of diverse, fully re-evaluated candidates.

This alpha repository is private and not approved for PyPI publication. It makes computational
design and scoring claims only; it does not establish binding, expression, promoter function,
regulatory grammar, synthesis readiness, or global optimality. Its larger-space search is an
executable synthetic tracer, not the legacy Cruncher Sample optimizer; optimizer parity,
adoption, and cutover remain explicitly unproven.

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

See [the documentation route](docs/index.md) for motif conversion, score interpretation,
artifact verification, limitations, and the manuscript-evidence boundary. Run
`bash ./scripts/agent-verify` for the same package gate used by CI.
