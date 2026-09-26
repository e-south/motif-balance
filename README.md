# ![Motif Balance: balanced motif design](https://raw.githubusercontent.com/e-south/motif-balance/main/assets/motif-balance-banner.svg)

Supply motif models and a DNA length. Motif Balance searches for sequences that
strengthen the weakest desired match while optionally limiting unwanted matches.
Inspect the recovered sites, choose different arrangements, then vary the sequence
within one selected arrangement. Scores describe agreement with the supplied
models, not measured binding.

[Documentation](https://github.com/e-south/motif-balance/blob/main/docs/README.md) ·
[Supply motifs](https://github.com/e-south/motif-balance/blob/main/docs/motif-models.md) ·
[Python API](https://github.com/e-south/motif-balance/blob/main/docs/python-api.md) ·
[Recorded twelve-model example](https://github.com/e-south/motif-balance/blob/main/docs/biological-example.md)

## Try a design

Fit the *E. coli* ArgR and Cra preferences into 32 bases. Their motif models span
25 and 14 positions, so their matches must share some DNA. The profiles come from
[Baumgart et al. (2021), Supplementary Data 2](https://doi.org/10.1038/s41592-021-01312-2),
which reports preferences inferred from DAP-seq.

### 1. Install and prepare the profiles

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```bash
# Create your own Python project and install Motif Balance from PyPI.
uv init --python 3.12 motif-example
cd motif-example
uv add motif-balance

# Download this release's example recipe and its source/checksum record.
curl -fLO https://raw.githubusercontent.com/e-south/motif-balance/v0.6.0/examples/argr-cra/prepare_inputs.py
curl -fLO https://raw.githubusercontent.com/e-south/motif-balance/v0.6.0/examples/argr-cra/SOURCE.json

# Fetch the publisher's data, verify it, and prepare the two local motif files.
uv run python prepare_inputs.py --out inputs
```

The [preparation record](https://github.com/e-south/motif-balance/blob/main/examples/argr-cra/README.md)
explains how source probabilities become positive scoring probabilities. uv manages
the environment and records the package dependency in your project.

### 2. Design and inspect DNA

Save this as `design.py`. A request names the desired models, DNA length, and
search allowance. Each candidate is scanned on both strands; its balance is the
weaker of the two best matches, each rescaled to its model's possible score range.

```python
from motif_balance import DesignSpec, MotifSpecification, design
from motif_balance.formats.motif import read_motif

# Load the two prepared profiles. Each position retains preferences for A, C, G, and T.
argr = read_motif("inputs/motifs/argR.json")
cra = read_motif("inputs/motifs/cra.json")

# Seek strong matches to both models within the same 32-base sequence.
spec = DesignSpec(
    specifications=(
        MotifSpecification(motif=argr, direction="seek"),
        MotifSpecification(motif=cra, direction="seek"),
    ),
    length=32,          # Available DNA in base pairs.
    count=4,            # Number of candidate sequences to return.
    evaluations=4096,  # Allowance for complete-sequence scores, shared by this run.
    seed=7,             # Repeat the same starting choices and search proposals.
)

# Search, save the result, and print each candidate's sequence and balance.
result = design(spec)
result.write("result")
for candidate in result.candidates:
    print(candidate.sequence, round(candidate.balance_score, 3))
```

Run the script and draw the best candidate:

```bash
# Run the search in your project's environment.
uv run python design.py

# Rescore the saved candidate and draw its sites and motif logos on a duplex.
uv run motif-balance inspect result --format svg --view candidate --out candidate.svg
```

Open `candidate.svg` in an image viewer. This run's best balance is about **0.880**.
Use new output names when repeating a run. SVG and HTML inspection need no extra
packages; [Installation](https://github.com/e-south/motif-balance/blob/main/docs/installation.md)
covers optional PNG, GIF, and MP4 support and ordinary pip installation.

### 3. Select different site arrangements

Different sequences can have the same relative motif placement. Append this to
`design.py` before running it, or continue in the same Python session:

```python
from motif_balance.alternatives import rank_architectures

# Use the sequences retained during search, including alternatives beyond the four returned.
pool = tuple(item.sequence for item in result.manifest.elites)

# Group by site order, strand, and overlap, then select two representatives.
ranking = rank_architectures(pool, spec, grouping="interval_topology")
selected = ranking.select(2)
for representative in selected:
    print(representative.sequence, round(representative.balance_score, 3))
```

These representatives score about **0.880** and **0.823**. Selection rescans the
saved pool without running another search. `select(2)` requires two available
arrangements; [collections](https://github.com/e-south/motif-balance/blob/main/docs/choose-alternatives.md)
explains how to allow and report a shortfall.

### 4. Vary a sequence within one arrangement

Continue with the first selected representative. The aim is now nucleotide
variation while retaining each desired model's selected site and score.

```python
from pathlib import Path
from motif_balance.variants import diversify
from motif_balance.formats.variants import variants_fasta, variants_tsv

# Protect each selected site's position and strand, allowing at most 0.02 score loss per model.
library = diversify(selected[0].sequence, spec, max_score_loss=0.02, max_variants=256)

# The compact template encodes exactly the concrete sequences checked together.
print(library.template, library.encoded_sequence_count)
print(library.minimum_balance, library.maximum_component_loss)

# Export every variant, its scores, and the complete verification record.
with Path("variants.fasta").open("x") as output:
    output.write(variants_fasta(library))
with Path("variant-scores.tsv").open("x") as output:
    output.write(variants_tsv(library))
with Path("library.json").open("x") as output:
    output.write(library.model_dump_json(indent=2))
```

This parent yields **eight checked sequences**, with balance no lower than about
**0.863**. The cap includes the parent; other designs may yield only that parent.
The tolerance concerns model scores, not binding affinity. See
[diversification](https://github.com/e-south/motif-balance/blob/main/docs/diversify-sequences.md)
for editable positions and the substitution map.

## Inspect a larger design

The [twelve-model example](https://github.com/e-south/motif-balance/blob/main/docs/biological-example.md)
shows a recorded search in 60-base DNA. Playback connects saved states with smooth
motion; displayed scores remain those of recorded sequences.

![Recorded twelve-model search with aligned motif matches](https://raw.githubusercontent.com/e-south/motif-balance/main/examples/twelve-motifs/playback.gif)

Motif Balance supports Python 3.12–3.14 on Linux and macOS.
See [Contributing](https://github.com/e-south/motif-balance/blob/main/CONTRIBUTING.md)
for development and [LICENSE](https://github.com/e-south/motif-balance/blob/main/LICENSE)
for software reuse. If you use Motif Balance in research, cite the accompanying
paper when available.
