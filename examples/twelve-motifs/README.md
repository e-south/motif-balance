# Twelve motif models in 60 DNA bases

Design one 60-base sequence with matches to twelve *E. coli* motif models. Each candidate is scanned on both strands. Its balance is the weakest of the twelve normalized best matches.

![Recorded best DNA and its motif matches](playback.gif)

[Download MP4](playback.mp4)

The complete seed-839 run used 655,360 evaluations and reached balance **0.733**. Search took 27.3 minutes on an Apple M2 Pro with 16 GiB memory during other workstation activity.

The blue curve follows the best balance encountered, and the orange point identifies the displayed DNA. The movie ends at evaluation 121,534, when the search reaches its final best score.

Faint gray motif windows show eight current search candidates behind the best DNA.

## Design with your own request

```bash
uv run motif-balance example twelve-motifs --out twelve-motifs
# Replace motif paths or change length and evaluations in design.yaml.
uv run motif-balance design twelve-motifs/design.yaml --out twelve-result
uv run motif-balance inspect twelve-result --format png --out twelve-dna.png
```

PNG export requires the visualization extra.

## Replay the recorded search

Use a separate checkout of the recorded recipe's release:

```bash
git clone --branch v0.8.1 --depth 1 https://github.com/e-south/motif-balance.git motif-balance-replay
cd motif-balance-replay
uv sync --locked --extra visualization

# Prepare the recorded models and check the request before searching.
uv run python examples/twelve-motifs/prepare_inputs.py
uv run motif-balance design examples/twelve-motifs/design.yaml --check
# Repeat the search, then export a player, MP4, GIF, and final frame.
uv run python examples/twelve-motifs/reproduce.py --out twelve-motifs-demo --media
```

Open `twelve-motifs-demo/playback.html` for play/pause and frame selection. Use a
new output directory. The recipe checks the recovered sequence and balance
against `expected.json`. Its evenly spaced search snapshots differ from the
published movie's denser early sampling. The [media record](media.json) lists
the movie's separately recorded frames and rendering settings.

## Motif inputs

The models are nucleotide probabilities inferred from DAP-seq in [Baumgart et al. (2021), Supplementary Data 2](https://doi.org/10.1038/s41592-021-01312-2). The [source record](../../src/motif_balance/examples/data/twelve-motifs/SOURCE.json) identifies the profiles and checksums. Preparation normalizes each row, then mixes it with a uniform distribution using weight 1/11. The scoring background is 0.25 per base.

| Model | Width in bases |
| --- | ---: |
| nagC | 21 |
| kdpE | 22 |
| sgrR | 15 |
| nadR | 20 |
| dpiA | 32 |
| iscR | 24 |
| cra | 14 |
| alsR | 21 |
| modE | 12 |
| nsrR | 31 |
| csiR | 24 |
| mntR | 13 |

Source and prepared matrices are written to `inputs/` during preparation.
