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

https://github.com/user-attachments/assets/dfbfdb47-a784-42db-b53e-81a32f640d08

The left plot follows the best balance found. On the right, the same twelve motif models change their best-match positions and strands along one continuous duplex. The final candidate has balance **0.724**. The declared seed-839 run provides one achieved arrangement to inspect. [Inspect the final sequence](../examples/twelve-motifs/final-frame.png) for the nucleotide sequence and individual match windows.

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

The request uses 65,536 complete candidate evaluations. Its recorded run took about 178 seconds elapsed on an Apple M2 Pro with 16 GiB memory while eight workers ran concurrently. Runtime on another machine will differ.

Open `playback.html` in the output directory to pause, scrub and inspect individual states. The video plays directly in this GitHub page. A [GIF preview](../examples/twelve-motifs/playback.gif) and the [MP4 file](../examples/twelve-motifs/playback.mp4) are also available. The horizontal axis counts candidate evaluations on a logarithmic scale, not elapsed time. Pauses show the seven recorded states. Between them, motif drawings move and crossfade; these labeled transitions do not supply intermediate DNA sequences or scores. Viewing intervals are not elapsed search time. The blue curve records the best balance so far, and the moving marker identifies the displayed state.

The final sequence establishes that these model scores were attained. It does not establish a best possible sequence or biological activity. To ask a different question, copy the request and change its DNA length, supplied models or evaluation allowance. To request distinct arrangements, use [collections](choose-alternatives.md).
