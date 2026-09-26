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

Fit the *E. coli* ArgR and Cra preferences into 25 bases. Their motif models span
25 and 14 positions, so the shorter match must fit within the same DNA as the
wider one. These profiles were inferred from the DAP-seq data in
[Baumgart et al. (2021), Supplementary Data 2](https://doi.org/10.1038/s41592-021-01312-2).

### 1. Install and prepare the profiles

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```bash
# Create a project and install the package from PyPI.
uv init --python 3.12 motif-example
cd motif-example
uv add 'motif-balance>=0.7.0'

# Fetch the attributed example, its source record, and its editable design request.
MB_EXAMPLE_URL=https://raw.githubusercontent.com/e-south/motif-balance/v0.6.0/examples/argr-cra
curl -fLO "$MB_EXAMPLE_URL/prepare_inputs.py"
curl -fLO "$MB_EXAMPLE_URL/SOURCE.json"
curl -fLO "$MB_EXAMPLE_URL/design.yaml"

# Check the publisher's data and prepare local ArgR and Cra models.
uv run python prepare_inputs.py --out inputs
```

`design.yaml` requests four 25-base sequences, 4,096 candidate evaluations, and
seed 7. Edit that file to change the request. The
[preparation record](https://github.com/e-south/motif-balance/blob/main/examples/argr-cra/README.md)
explains the probability adjustment and source checks.

### 2. Design and inspect DNA

```bash
# Search for DNA with a strong weakest motif match, and save its sequences and scores.
uv run motif-balance design design.yaml --out result

# Draw the selected sites and logos, with the score and search summaries alongside.
uv run motif-balance inspect result --format html --out review.html
```

Open `review.html`. The best candidate scores about **0.855**. The review shows
where each motif matches, on which strand, and how well it scores. Every candidate
is scanned on both strands. These scores measure agreement with the models.

### 3. Collect different arrangements

```bash
# Keep up to two representatives with different motif order, strand, or overlap.
uv run motif-balance collect result --count 2 --out collection.json
```

The representatives score about **0.855** and **0.801**. Collection selection uses
the retained search pool and reports any shortfall. It does not run another search.
The saved collection carries its sequences, motif models, and selected sites.
[Arrangement definitions](https://github.com/e-south/motif-balance/blob/main/docs/choose-alternatives.md)
explain which differences count.

### 4. Diversify one selected sequence

```bash
# Vary the first representative while keeping its selected sites fixed.
# Each motif may lose at most 0.02 on its normalized score scale.
uv run motif-balance diversify collection.json --candidate 1 \
  --max-score-loss 0.02 --out variants
```

This parent yields **16 checked sequences**, with balance no lower than about
**0.838**. Open `variants/substitutions.svg` to see the nucleotide choices. The same
directory contains `variants.fasta`, `scores.tsv`, and the full `library.json`.
Every sequence encoded by its ambiguity template is checked. Other parents can
yield only the parent itself; the tolerance does not guarantee preserved binding.

Use a new output name when repeating a step. For custom motifs, start with
[motif inputs](https://github.com/e-south/motif-balance/blob/main/docs/motif-models.md).
For notebooks and programmable workflows, use the
[Python tutorial](https://github.com/e-south/motif-balance/blob/main/docs/python-api.md).
[Installation](https://github.com/e-south/motif-balance/blob/main/docs/installation.md)
also covers ordinary pip and optional video export.

## Inspect a larger design

The [twelve-model example](https://github.com/e-south/motif-balance/blob/main/docs/biological-example.md)
shows a recorded search in 60-base DNA. Playback connects saved states with smooth
motion; displayed scores remain those of recorded sequences. The best-so-far chart is on the left; the continuous duplex and
its strand-aligned motif windows are on the right.

https://github.com/user-attachments/assets/fa2dd454-7f39-433d-8f60-d221c6247169

[Full-resolution MP4](https://github.com/e-south/motif-balance/raw/refs/heads/main/examples/twelve-motifs/playback.mp4) · [Inspect the final sequence](https://github.com/e-south/motif-balance/blob/main/examples/twelve-motifs/final-frame.png)

Motif Balance supports Python 3.12–3.14 on Linux and macOS.
See [Contributing](https://github.com/e-south/motif-balance/blob/main/CONTRIBUTING.md)
for development and [LICENSE](https://github.com/e-south/motif-balance/blob/main/LICENSE)
for software reuse. If you use Motif Balance in research, cite the accompanying
paper when available.
