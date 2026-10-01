# ![Motif Balance: balanced motif design](https://raw.githubusercontent.com/e-south/motif-balance/main/assets/motif-balance-banner.svg)

Supply motif models and a DNA length. Motif Balance searches for sequences that
strengthen the weakest desired match while optionally limiting unwanted matches.
Inspect the recovered sites, choose different arrangements, then expand each
selected layout into nucleotide alternatives. Scores describe agreement with the supplied
models, not measured binding.

[Documentation](https://github.com/e-south/motif-balance/blob/main/docs/README.md) ·
[Supply motifs](https://github.com/e-south/motif-balance/blob/main/docs/motif-models.md) ·
[Python API](https://github.com/e-south/motif-balance/blob/main/docs/python-api.md) ·
[Recorded twelve-model example](https://github.com/e-south/motif-balance/blob/main/examples/twelve-motifs/README.md)

## Try a design

Fit the *E. coli* ArgR and Cra preferences into 25 bases. Their motif models span
25 and 14 positions, so the shorter match must fit within the same DNA as the
wider one. These profiles were inferred from the DAP-seq data in
[Baumgart et al. (2021), Supplementary Data 2](https://doi.org/10.1038/s41592-021-01312-2).

### 1. Install and prepare the profiles

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```bash
# Create a project and install the package from PyPI.
uv init --python 3.12 my-project
cd my-project
uv add 'motif-balance==0.8.0'

# Fetch the attributed example, its source record, and its editable design request.
MB_EXAMPLE_URL=https://raw.githubusercontent.com/e-south/motif-balance/v0.8.0/examples/argr-cra
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
is scanned on both strands.

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

### 4. Expand each arrangement into sequence alternatives

```bash
# Vary nucleotides within each layout while retaining its selected motif sites.
# Every returned sequence must have balance at least 0.8.
uv run motif-balance expand collection.json --all --min-balance 0.8 --out expanded
```

Each arrangement returns **256 sequences** at the default output limit. Every
sequence meets the 0.8 floor and retains its parent's selected motif positions
and strands. Open the FASTA and per-motif score table for each arrangement in
`expanded/`; `collection.json` contains the complete record. Other designs can
yield fewer alternatives.

[Sequence expansion](https://github.com/e-south/motif-balance/blob/main/docs/expand-sequences.md)
explains the score floor and work limits. For synthesis as a checked ambiguity
template, use the separate [degenerate-library operation](https://github.com/e-south/motif-balance/blob/main/docs/diversify-sequences.md).

Use a new output name when repeating a step. For custom motifs, start with
[motif inputs](https://github.com/e-south/motif-balance/blob/main/docs/motif-models.md).
For notebooks and programmable workflows, use the
[Python tutorial](https://github.com/e-south/motif-balance/blob/main/docs/python-api.md).
[Installation](https://github.com/e-south/motif-balance/blob/main/docs/installation.md)
also covers ordinary pip and optional video export.

## Inspect a larger design

The [twelve-model example](https://github.com/e-south/motif-balance/blob/main/examples/twelve-motifs/README.md)
shows a recorded search in 60-base DNA. Playback connects saved states with smooth
motion; displayed scores remain those of recorded sequences. The best-so-far chart is on the left; the continuous duplex and
its strand-aligned motif windows are on the right.

![Recorded improvements in the twelve-model search](https://github.com/e-south/motif-balance/raw/refs/heads/main/examples/twelve-motifs/playback.gif)

[Full-resolution MP4](https://github.com/e-south/motif-balance/raw/refs/heads/main/examples/twelve-motifs/playback.mp4) · [Inspect the final sequence](https://github.com/e-south/motif-balance/blob/main/examples/twelve-motifs/final-frame.png)

Motif Balance supports Python 3.12–3.14 on Linux and macOS.
See [Contributing](https://github.com/e-south/motif-balance/blob/main/CONTRIBUTING.md)
for development and [LICENSE](https://github.com/e-south/motif-balance/blob/main/LICENSE)
for software reuse. [Cite Motif Balance](https://github.com/e-south/motif-balance/blob/main/CITATION.cff)
with the version used in your analysis.
