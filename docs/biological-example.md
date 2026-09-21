---
doc_id: motif-balance-biological-example
title: Fit three motifs into 20 DNA bases
intent: Follow a compact three-profile design and inspect recorded search progress.
audience: [users]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-21
doc_type: tutorial
---

# Fit three motifs into 20 DNA bases

Dorsal, Twist and Zelda regulate transcription in the early fly embryo. Their
binding sites have been studied together in the *snail* distal enhancer
([Syed et al., 2023](https://elifesciences.org/articles/85997)). Here, we ask how
these three motif preferences can share a short DNA sequence.

<a href="../examples/developmental-trio/playback.mp4"><img src="../examples/developmental-trio/final-frame.png" width="640" alt="Three motif matches beside the recorded search curve; click to open the video"></a>

[Watch the video](../examples/developmental-trio/playback.mp4) ·
[Open the vector figure](../examples/developmental-trio/final-frame.svg)

## 1. Supply the motifs and available DNA

The bundled [request](../examples/developmental-trio/design.yaml) uses these
JASPAR profiles:

| Motif | Profile | Width |
| --- | --- | --- |
| Dorsal | [MA0022.1](https://jaspar.elixir.no/matrix/MA0022.1/) | 12 bases |
| Twist | [MA0249.3](https://jaspar.elixir.no/matrix/MA0249.3/) | 7 bases |
| Zelda (source name `vfl`) | [MA1462.2](https://jaspar.elixir.no/matrix/MA1462.2/) | 7 bases |

Their widths total 26 bases. A 20-base design therefore requires some matches
to share positions. The search chooses the DNA; scanning both strands determines
each motif's strongest match. The [example sources](../examples/developmental-trio/README.md#input-provenance-and-interpretation)
include the count matrices, probability conversion and attribution.

## 2. Design and view one candidate

From the [installed source checkout](installation.md#install-from-source):

```bash
# Check that all three profiles fit the requested DNA length and search budget.
uv run motif-balance design examples/developmental-trio/design.yaml --check

# Search with seed 7 and a budget of 4,096 candidate evaluations.
uv run motif-balance design examples/developmental-trio/design.yaml \
  --out /tmp/developmental-trio-result

# Draw the selected motif matches, both DNA strands and aligned logos.
uv run motif-balance inspect /tmp/developmental-trio-result \
  --format svg --view candidate --out /tmp/developmental-trio-candidate.svg
```

Open the SVG to inspect the matches. The budget samples only a small part of the
20-base sequence space, so this is a recovered candidate, not a proven optimum.
Use new output paths when repeating the commands.

## 3. Watch how the recovered sequence changes

```bash
# Repeat the example while saving the observed states, player and video.
uv run python examples/developmental-trio/reproduce.py \
  --out /tmp/developmental-trio-demo --media
```

Open the generated HTML player or MP4. The orange point marks the score and
evaluation count of the displayed DNA. Each recorded state receives equal viewing
time; horizontal spacing reflects evaluation counts on the logarithmic axis.
See [playback](reference/playback.md) to render your own search.

## Try a different constraint

| Change in a copied request | Design question |
| --- | --- |
| `length: 26` | Can the motifs occupy separate windows? |
| `length: 12` | Can all three fit within the longest motif span? |
| A different `seed` | Does another search recover a different solution? |

Search each request independently. To retain different motif arrangements from
a search, use [collections](choose-alternatives.md).
