---
doc_id: motif-balance-biological-example
title: Follow twelve motif preferences in one DNA search
intent: Prepare biological profiles, search at fixed length, and inspect recorded improvement.
audience: [users]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-26
doc_type: tutorial
---

# Follow twelve motif preferences in one DNA search

A motif describes alternative bases at each position. When twelve models share a 60-base sequence, their preferred windows may overlap and compete for the same bases. This example searches for DNA whose weakest relative match is strong.

https://github.com/user-attachments/assets/a6408061-1620-473f-85c8-e29dabfe9d54

The left plot separates the changing balance of one current search candidate in gray from the highest balance found so far in blue. The faint gray placements on the right follow that same current candidate; the colored duplex retains the best DNA. Each motif score *qᵢ* is its normalized best match. Balance *B(s)* is the weakest score for sequence *s*, and *B* with subscript “best” is the largest balance encountered so far. The final candidate has balance **0.733**. [Inspect the final sequence](../examples/twelve-motifs/final-frame.png) for its nucleotide sequence and motif windows.

## Prepare the models

The twelve *E. coli* probability profiles come from Baumgart et al. (2021), Supplementary Data 2. The [input record](../examples/twelve-motifs/README.md#inputs-and-interpretation) lists model widths, source attribution and the exact preparation. From the [installed source checkout](installation.md#install-from-source), run:

```bash
# Prepare the twelve published profiles using the recorded source and checksum.
uv run python examples/twelve-motifs/prepare_inputs.py
# Check that the request and all model files are valid before searching.
uv run motif-balance design examples/twelve-motifs/design.yaml --check
```

The preparation script downloads a checksum-verified archive and generates the local models. A request fixes the models, desired roles, DNA length, seed and evaluation allowance. Best-match positions and strands are determined by scanning each proposed sequence.

## Run and inspect the search

```bash
# Repeat the saved request and export its player, movie, preview, and final sequence view.
uv run python examples/twelve-motifs/reproduce.py --out /tmp/twelve-motifs-demo --media
```

The request uses 655,360 complete candidate evaluations. The recorded search took 27.3 minutes elapsed and 0.452 CPU hours in one process on an Apple M2 Pro with 16 GiB memory. Other workstation activity continued during the run. This excludes replay and rendering.

At one tenth of this allowance, the same models and seed recovered balance 0.724. The longer request recovered 0.733. It starts afresh with schedules spread across the larger budget; it does not resume the earlier trajectory. This is one computational example, not an estimate of the improvement expected for other requests.

The video plays directly in this GitHub page. A [GIF preview](../examples/twelve-motifs/playback.gif) and the [MP4 file](../examples/twelve-motifs/playback.mp4) are also available. Open `playback.html` in the output directory to inspect an eight-frame overview. The movie uses 113 verified observations, with 95 distinct current sequences and 12 distinct best sequences. Gray follows one fixed candidate among the eight maintained by this search, not every tested proposal. All eight share the same evaluation budget.

The horizontal axis counts candidate evaluations on a logarithmic scale. At 30 frames per second, four display transitions connect successive changed drawings without checkpoint pauses. These transitions move and crossfade endpoint drawings; they do not supply intermediate scored DNA. Scores change only at actual observations. Viewing time does not represent search time.

The final sequence establishes that these model scores were attained. It does not establish a best possible sequence or biological activity. To ask a different question, copy the request and change its DNA length, supplied models or evaluation allowance. To request distinct arrangements, use [collections](choose-alternatives.md).
