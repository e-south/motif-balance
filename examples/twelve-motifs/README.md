# Twelve motif models in 60 DNA bases

The recorded search asks one 60-base sequence to agree with twelve supplied *E. coli* motif models. Every candidate is scanned on both strands. Its balance is the weakest of the twelve normalized best matches.

https://github.com/user-attachments/assets/11f7d777-e4dd-43aa-854c-24d4552d198d

[MP4](playback.mp4) · [GIF](playback.gif) · [Inspect the final frame](final-frame.png) · [Step-by-step guide](../../docs/biological-example.md)

The seed-839 search uses 655,360 evaluations and produces the displayed candidate with balance **0.733**. It took 27.3 minutes elapsed and 0.452 CPU hours in one process on an Apple M2 Pro with 16 GiB memory, during other workstation activity. Peak search memory was 128.8 MiB. These measurements exclude verification replay and rendering.

This is a fresh search with ten times the earlier evaluation allowance. The same models and seed previously recovered balance 0.724 at 65,536 evaluations. The larger allowance stretches the proposal and acceptance schedules, so the new run is not a continuation of that trajectory. This one comparison illustrates an achieved improvement; it does not establish a general compute-response curve.

The eight gray traces follow the candidate sequences maintained by the search; blue records the best balance encountered. Their faint placements move behind the colored best DNA. All eight share one evaluation budget. These snapshots omit intermediate proposals, so their current scores need not meet the best-so-far point.

The movie ends at 125,497 evaluations, the first saved observation containing the final best score. Its 33 observations include twelve distinct best sequences. The axis ends there too; the complete run still used 655,360 evaluations. Motion starts slowly and accelerates, while scores update only at recorded observations. Viewing time is not elapsed search time. The small HTML overview shows eight best-sequence frames.

## Reproduce

From the installed source checkout with the visualization extra:

```bash
# Prepare the recorded models and check the request before searching.
uv run python examples/twelve-motifs/prepare_inputs.py
uv run motif-balance design examples/twelve-motifs/design.yaml --check
# Repeat the search, then export a player, MP4, GIF, and final frame.
uv run python examples/twelve-motifs/reproduce.py --out /tmp/twelve-motifs-demo --media
```

Open the generated `playback.html` for play/pause and frame selection, or use the inline video above. Outputs must use a new directory. `expected.json` records the selected sequence, score, seed and software version; the reproduction script checks the declared replay package before search and the resulting sequence and balance afterward. Motif Balance 0.7.0 reproduced the complete recorded observation history exactly. The original run used Python 3.12.14 and working source based on revision `9147a98`, with the expanded single-result budget limits subsequently released in 0.7.0. `expected.json` distinguishes the producing source from the replay version.

## Inputs and interpretation

The models are numerical probability records from [Baumgart et al. (2021), Supplementary Data 2](https://doi.org/10.1038/s41592-021-01312-2), inferred from DAP-seq. [SOURCE.json](SOURCE.json) identifies the archive, records, checksums and preparation. The recipe normalizes each row, then mixes it with a uniform distribution using weight 1/11. The scoring background is 0.25 per base.

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

Source and prepared matrices are downloaded into ignored `inputs/`, rather than distributed with the repository. The animation and PNG are newly generated artwork. Editable SVGs containing exact probability metadata are generated only on the caller’s machine. The input set supplies a computational sharing problem, without asserting that these factors jointly regulate a native sequence. Scores measure agreement with the supplied models, not binding or expression.
