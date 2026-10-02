# Twelve motif models in 60 DNA bases

The recorded search asks one 60-base sequence to agree with twelve supplied *E. coli* motif models. Every candidate is scanned on both strands. Its balance is the weakest of the twelve normalized best matches.

![Recorded best DNA and its motif matches](playback.gif)

[MP4](playback.mp4) · [GIF](playback.gif) · [Inspect the final frame](final-frame.png) · [Source installation](../../docs/installation.md#install-from-source)

The seed-839 search uses 655,360 evaluations and produces the displayed candidate with balance **0.733**. It took 27.3 minutes elapsed and 0.452 CPU hours in one process on an Apple M2 Pro with 16 GiB memory, during other workstation activity. Peak search memory was 128.8 MiB. These measurements exclude verification replay and rendering.

The blue curve follows the best balance encountered, and the orange point identifies the displayed DNA. Nineteen recorded best sequences lead to the final score at 121,534 evaluations, where the movie and axis end. The complete run still used 655,360 evaluations. The subtitle gives its measured full-run elapsed time, not the unknown wall time at each improvement.

Faint gray motif windows show the eight recorded search candidates behind the best DNA. Their scores are omitted from the chart. Transitions start slowly and accelerate between recorded placements.

The inline GIF is 1,000 pixels wide; the MP4 is 1,800 pixels wide. The movie uses denser early observations from the recorded run. The recipe below repeats the search with evenly spaced snapshots, so its gray-state timing differs while the recovered sequence and score are checked.

## Design with your own request

```bash
uv run motif-balance example twelve-motifs --out twelve-motifs
# Replace motif paths or change length and evaluations in design.yaml.
uv run motif-balance design twelve-motifs/design.yaml --out twelve-result
uv run motif-balance inspect twelve-result --format png --out twelve-dna.png
```

This uses the installed package and an editable request. PNG export requires
the visualization extra. New requests are not compared against the recorded winner.

## Replay the recorded search

From the installed source checkout with the visualization extra:

```bash
# Prepare the recorded models and check the request before searching.
uv run python examples/twelve-motifs/prepare_inputs.py
uv run motif-balance design examples/twelve-motifs/design.yaml --check
# Repeat the search, then export a player, MP4, GIF, and final frame.
uv run python examples/twelve-motifs/reproduce.py --out /tmp/twelve-motifs-demo --media
```

Open `playback.html` for play/pause and frame selection. Use a new output directory. The recipe requires Motif Balance 0.8.1 and checks the recovered sequence and balance against `expected.json`, which also records the original producing source and independently verified 0.7.0 replay.

## Inputs and interpretation

The models are numerical probability records from [Baumgart et al. (2021), Supplementary Data 2](https://doi.org/10.1038/s41592-021-01312-2), inferred from DAP-seq. [source record](../../src/motif_balance/examples/data/twelve-motifs/SOURCE.json) identifies the archive, records, checksums and preparation. The recipe normalizes each row, then mixes it with a uniform distribution using weight 1/11. The scoring background is 0.25 per base.

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

Source and prepared matrices are downloaded into ignored `inputs/`. The repository distributes rendered artwork; editable SVGs containing exact probabilities are generated locally. The example tests sharing DNA space among these models, not joint regulation of a native sequence. Scores measure model agreement, not binding or expression.
