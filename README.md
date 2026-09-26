# ![Motif Balance: balanced motif design](https://raw.githubusercontent.com/e-south/motif-balance/main/assets/motif-balance-banner.svg)

Supply motif models and a DNA length. Motif Balance searches for sequences that
strengthen the weakest desired match while optionally limiting unwanted matches.
Inspect each motif's best-matching site, strand, and score, then select different
arrangements or diversify one selected sequence within its score limits.
The scores describe agreement with the supplied models, not measured binding.

[Documentation](https://github.com/e-south/motif-balance/blob/main/docs/README.md) ·
[Biological example](https://github.com/e-south/motif-balance/blob/main/docs/biological-example.md) ·
[Supply motifs](https://github.com/e-south/motif-balance/blob/main/docs/motif-models.md) ·
[Python API](https://github.com/e-south/motif-balance/blob/main/docs/python-api.md)

## Try a design

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed,
create a project and add Motif Balance from PyPI:

```bash
uv init --python 3.12 motif-example
cd motif-example
uv add motif-balance
```

Save the following as `design.py`. These two small, synthetic models make the
example self-contained. Each row gives the probabilities of A, C, G, and T at
one motif position.

```python
from motif_balance import DesignSpec, MotifModel, MotifSpecification, design

first = MotifModel(
    motif_id="first",
    probabilities=((0.7, 0.1, 0.1, 0.1), (0.1, 0.7, 0.1, 0.1),
                   (0.1, 0.1, 0.7, 0.1), (0.1, 0.1, 0.1, 0.7)),
    background=(0.25,) * 4,
)
second = MotifModel(
    motif_id="second",
    probabilities=((0.1, 0.7, 0.1, 0.1), (0.1, 0.1, 0.7, 0.1),
                   (0.7, 0.1, 0.1, 0.1), (0.1, 0.7, 0.1, 0.1)),
    background=(0.25,) * 4,
)
spec = DesignSpec(
    specifications=tuple(MotifSpecification(motif=m, direction="seek")
                         for m in (first, second)),
    length=6,
    count=4,
    evaluations=1024,
    seed=7,
)
result = design(spec)
result.write("result")
for candidate in result.candidates:
    print(candidate.sequence, round(candidate.balance_score, 3))
```

Run it, then draw the best candidate and its motif matches:

```bash
uv run python design.py
uv run motif-balance inspect result --format svg --view candidate --out candidate.svg
```

Open `candidate.svg` in an image viewer. Each candidate is scanned on both
strands. Its balance is the weakest motif match, with each match rescaled to
that model's possible score range. Use new output names when repeating a run.

uv manages the Python environment and records dependencies in the project.
For other installation options and optional PNG, GIF, and MP4 support, see
[Installation](https://github.com/e-south/motif-balance/blob/main/docs/installation.md).

## Explore the recovered sequences

- [Select arrangements](https://github.com/e-south/motif-balance/blob/main/docs/choose-alternatives.md)
  from retained candidates using site order, strand, and overlap.
- [Diversify a selected sequence](https://github.com/e-south/motif-balance/blob/main/docs/diversify-sequences.md)
  into a checked variant library while retaining selected desired sites and
  limiting every requested score's loss.
- [Use measured motif profiles](https://github.com/e-south/motif-balance/blob/main/docs/quickstart.md)
  in the attributed ArgR/Cra example.

The [twelve-model example](https://github.com/e-south/motif-balance/blob/main/docs/biological-example.md)
shows a recorded search in 60-base DNA. Playback connects saved states with
smooth motion; displayed scores remain those of recorded sequences.

![Recorded twelve-model search with aligned motif matches](https://raw.githubusercontent.com/e-south/motif-balance/main/examples/twelve-motifs/playback.gif)

Motif Balance supports Python 3.12–3.14 on Linux and macOS.
See [Contributing](https://github.com/e-south/motif-balance/blob/main/CONTRIBUTING.md)
for development and [LICENSE](https://github.com/e-south/motif-balance/blob/main/LICENSE)
for software reuse. If you use Motif Balance in research, cite the accompanying
paper when available.
