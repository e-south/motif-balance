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

The `visualization` extra adds **PNG images and GIF/MP4 search videos** showing
DNA edits, motif logos and the best balance recovered. SVG images and HTML views
work without it. See the [recorded example](https://github.com/e-south/motif-balance/blob/main/docs/biological-example.md).

**1. Load two TF motifs and design DNA.** ArgR and Cra are *E. coli* profiles
from [Baumgart et al. (2021), Supplementary Data 2](https://doi.org/10.1038/s41592-021-01312-2).
Their prepared `probabilities` give A, C, G and T probabilities at each motif
position. `specifications` pairs each model with a goal: `seek` strengthens its
best match; `avoid` reduces it. Both DNA strands are scanned.

```python
# Load the bundled profiles and define the design request.
from motif_balance import DesignSpec, MotifSpecification, design
from motif_balance.formats.motif import read_motif

argr = read_motif("examples/argr-cra/motifs/argR.json")  # 25-position ArgR model
cra = read_motif("examples/argr-cra/motifs/cra.json")    # 14-position Cra model
spec = DesignSpec(
    specifications=(                                     # Motif models and their goals
        MotifSpecification(motif=argr, direction="seek"),
        MotifSpecification(motif=cra, direction="seek"),
    ),
    length=32,                                           # DNA length in base pairs
    count=4,                                             # Number of sequences to return
    evaluations=4096,                                    # Maximum candidate evaluations
    seed=7,
)
result = design(spec)                                    # Search by editing and rescanning DNA
for candidate in result.candidates:
    print(candidate.sequence, round(candidate.balance_score, 3))
```

A candidate evaluation scans every motif across both strands and computes the
balance: the lowest of their best-match scores, each rescaled to that model's
possible score range from 0 to 1. This run returns four sequences; the best
balance is about **0.880**.

**2. Collect different arrangements.** Different sequences can place their
motif matches in the same way. Group the saved candidates by order, strand and
overlap, then select two arrangements:

```python
# Select arrangements from the sequences already evaluated.
from motif_balance.alternatives import rank_architectures

pool = tuple(c.sequence for c in result.manifest.elites)  # Retained search candidates
ranking = rank_architectures(pool, spec, grouping="interval_topology")
collection = ranking.select(2)                            # Best two distinct arrangements
for candidate in collection:
    print(candidate.sequence, round(candidate.balance_score, 3))
```

This collection has balances of about **0.880** and **0.823**. Selection rescans
the saved sequences; it does not run another search. See [First design](https://github.com/e-south/motif-balance/blob/main/docs/quickstart.md)
to save a result and view its motif matches, or the [input provenance](https://github.com/e-south/motif-balance/blob/main/examples/argr-cra/README.md)
for these two profiles.

The current prerelease supports Python 3.12–3.14 on Linux and macOS.
See [Contributing](https://github.com/e-south/motif-balance/blob/main/CONTRIBUTING.md) for development and [LICENSE](https://github.com/e-south/motif-balance/blob/main/LICENSE) for
software reuse.

If you use Motif Balance in your research, please cite the accompanying paper
when available.
