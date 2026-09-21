# ![Motif Balance: balanced motif design](https://raw.githubusercontent.com/e-south/motif-balance/main/assets/motif-balance-banner.svg)

Supply motif models and a DNA length. Motif Balance searches for sequences that
strengthen the weakest desired match while optionally limiting unwanted matches.
Results show each motif's best-matching site, strand and score, so you can compare
alternative arrangements.

[Install](https://github.com/e-south/motif-balance/blob/main/docs/installation.md) ·
[First design](https://github.com/e-south/motif-balance/blob/main/docs/quickstart.md) ·
[Example](https://github.com/e-south/motif-balance/blob/main/docs/biological-example.md) ·
[Supply motifs](https://github.com/e-south/motif-balance/blob/main/docs/motif-models.md) ·
[Python](https://github.com/e-south/motif-balance/blob/main/docs/python-api.md) ·
[Documentation](https://github.com/e-south/motif-balance/blob/main/docs/README.md)

## Try a design

With Git and [uv](https://docs.astral.sh/uv/) installed:

```bash
# Download the code and bundled examples.
git clone https://github.com/e-south/motif-balance.git
# Enter the project directory.
cd motif-balance
# Install the locked dependencies and image/video support.
uv sync --locked --extra visualization
# Open Python in this environment, then paste the examples below.
uv run python
```

**1. Define two motifs and design DNA.** These toy motifs prefer AA and CC.
Each matrix row gives the probabilities of A, C, G and T at one position.

```python
# Import the input models and sequence-design function.
from motif_balance import DesignSpec, MotifModel, MotifSpecification, design

# Give A the strongest preference at both positions.
left = MotifModel(
    motif_id="AA",
    probabilities=((0.7, 0.1, 0.1, 0.1),) * 2,
    background=(0.25,) * 4,
)
# Give C the strongest preference at both positions.
right = MotifModel(
    motif_id="CC",
    probabilities=((0.1, 0.7, 0.1, 0.1),) * 2,
    background=(0.25,) * 4,
)
# Fit both motifs into four bases, scanning both strands by default.
spec = DesignSpec(
    specifications=(
        MotifSpecification(motif=left, direction="seek"),
        MotifSpecification(motif=right, direction="seek"),
    ),
    length=4,
    count=4,
    evaluations=256,
    seed=7,
)
# Find four sequences, using the weakest motif match as their balance score.
result = design(spec)
# Print each returned sequence and its balance on the 0–1 model-score scale.
for candidate in result.candidates:
    print(candidate.sequence, round(candidate.balance_score, 3))
```

**2. Collect different arrangements.** Sequences can differ yet place their
motif matches in the same way. Select two arrangements from the saved search pool:

```python
# Import the selector that groups matches by order, strand and overlap.
from motif_balance.alternatives import rank_architectures

# Use the retained search pool, including sequences outside the four winners.
pool = tuple(candidate.sequence for candidate in result.manifest.elites)
# Keep the best sequence from each distinct arrangement.
ranking = rank_architectures(pool, spec, grouping="interval_topology")
# Request exactly two distinct arrangements.
collection = ranking.select(2)
# Display the selected sequences and their weakest motif-match scores.
for candidate in collection:
    print(candidate.sequence, round(candidate.balance_score, 3))
```

The collection contains `AACC` and `AAGG`, both with balance 1.0. In `AAGG`,
the CC motif matches the reverse strand.

This small example evaluates all 256 four-base sequences. For longer DNA,
`evaluations` limits the search effort. See [First design](https://github.com/e-south/motif-balance/blob/main/docs/quickstart.md)
to save a result and view its motif matches.

The current prerelease supports Python 3.12–3.14 on Linux and macOS.
See [Contributing](https://github.com/e-south/motif-balance/blob/main/CONTRIBUTING.md) for development and [LICENSE](https://github.com/e-south/motif-balance/blob/main/LICENSE) for
software reuse.

If you use Motif Balance in your research, please cite the accompanying paper
when available.
