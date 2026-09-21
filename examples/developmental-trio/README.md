---
doc_id: motif-balance-developmental-trio-example
title: Fit Dorsal, Twist and Zelda preferences into compact DNA
intent: Reproduce a biological motif example and inspect its recorded search states.
audience: users
status: active
doc_type: tutorial
---

# Fit Dorsal, Twist and Zelda preferences into compact DNA

Dorsal, Twist and Zelda regulate early *Drosophila melanogaster* development.
This example asks for a 20-base sequence matching all three supplied motif
models. Their widths are 12, 7 and 7 bases, so some matches must share positions.
The search chooses the DNA; best-match positions and strands emerge from rescanning.

<a href="playback.mp4"><img src="final-frame.png" width="640" alt="Three motif matches beside the recorded search curve; click to open the video"></a>

Read the [example guide](../../docs/biological-example.md) for the
installation and design steps. To reproduce the illustration from an installed
package, run this example directory's script from any working directory:

```bash
# Recreate the example search, its saved observations and its HTML player.
python reproduce.py --out /tmp/developmental-trio-demo
```

It creates the observation JSON, a self-contained HTML player, the final SVG
frame and a summary containing input identifiers and output hashes. The script
checks all three prepared matrices against the bundled source counts before search.
Output directories must be new. Add `--media` with the `visualization` extra
installed to create PNG, GIF and MP4 files as well. The player advances through
recorded observations; its timing does not represent search elapsed time.

For an existing observation file:

```bash
# Open the saved states through a new interactive HTML player.
motif-balance animate /tmp/developmental-trio-demo/observation.json --out /tmp/review.html
# Export the same saved states as an MP4 video.
motif-balance animate /tmp/developmental-trio-demo/observation.json --out /tmp/review.mp4 --format mp4
```

The default molecular panel follows the best sequence evaluated. Add `--chain 0`
to follow the first search chain, whose score may decrease during exploration.
The blue curve connects sampled best scores. The orange point marks the displayed
DNA, including its current score when following one chain. Unequal horizontal
spacing reflects saved evaluation counts on a logarithmic axis. Each snapshot
is displayed for the same duration; unchanged DNA can persist over several frames. Each frame's sequence and
selected windows are replayed before rendering. Random and exhaustive searches
do not have chains.

## Input provenance and interpretation

We use JASPAR CORE profiles [MA0022.1](https://jaspar.elixir.no/matrix/MA0022.1/)
for Dorsal, [MA0249.3](https://jaspar.elixir.no/matrix/MA0249.3/) for Twist and
[MA1462.2](https://jaspar.elixir.no/matrix/MA1462.2/) for Zelda (source name `vfl`).
The source count matrices are retained in `source/`. The prepared probability
matrices in `motifs/` use the package's explicit JASPAR conversion: add a total
pseudocount of the square root of the column count, divided equally among the
four bases, then divide by the new total. All three use a uniform scoring background.
Each prepared model records the source identifier, source digest and conversion.

The demonstration fixes a 4,096-evaluation budget and seed 7 to keep a single
run quick and repeatable. Those choices illustrate the interface; they were not
tuned to establish comparative search performance. The generated sequence is a
model-based design candidate, not an experimentally validated enhancer.

JASPAR data are attributed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
The raw profiles are unchanged; probability conversion and all illustrations
are generated here. See [SOURCE.json](SOURCE.json) for the exact download URLs,
source checksums and retrieval date. Code is covered by the repository MIT
license. The derived example images and video are CC BY 4.0, attributed to
Eric J. South, Dunlop Lab, with underlying profiles credited to JASPAR.

Biological context: Syed S, Duan Y, Lim B (2023),
[Modulation of protein-DNA binding reveals mechanisms of spatiotemporal gene
control in early Drosophila embryos](https://elifesciences.org/articles/85997).
