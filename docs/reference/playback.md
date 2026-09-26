---
doc_id: motif-balance-playback
title: Show a recorded search
intent: Render recorded sequence states alongside best observed scores.
audience: [users]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-26
doc_type: how-to
---

# Show a recorded search

A score curve shows whether search improves, while the corresponding DNA view
shows how the selected motif matches change. Playback joins these views using
[search observations](search-observations.md) from one run. It replays the
observation before rendering, so altered sequence or score records fail validation.

## Export an observation

The [example](../biological-example.md) creates an observation file.
For a file saved from your own `design_observed` call:

```bash
# Create an interactive player from the recorded search states.
motif-balance animate observation.json --out playback.html
# Export the final recorded state as a vector figure.
motif-balance animate observation.json --format svg --out final-frame.svg
```

HTML provides local playback controls. SVG exports the final recorded frame;
choose another zero-based index with `--frame`. Output files must be new, and
the suffix must match the selected format.

By default the molecule is the best sequence evaluated so far at each recorded
snapshot or exact incumbent checkpoint. The default view combines these records
in evaluation order, counting a shared checkpoint once. `--chain 0` instead follows one fixed, zero-based search-chain identity;
its current score can decrease. The best-so-far curve remains separate from that
current state. Uniform random sampling and complete enumeration have no search
chains. Missing chains or unsupported frames are rejected.

The blue curve connects recorded snapshots. The orange point gives the score
and evaluation count for the displayed DNA. Unequal spacing comes from the
recorded counts on a logarithmic axis. HTML presents these observations at the
chosen viewing rate.
For up to eight models, the two views have equal square content areas, with the
duplex scale and DNA baselines fixed across the recording. This layout exports at
1,920 × 1,056 pixels. For nine to twelve models, a larger square recovery plot sits on the left of a
continuous molecular view, with presentation-sized axis labels. The score above
the orange point gives the displayed candidate's balance. For the best-sequence
view it is labeled *B* with subscript “best” and evaluation count *e*. Balance
*B(s)* is the minimum normalized motif score *qᵢ(s)* for DNA sequence *s*. The
best-so-far value is the largest balance encountered through *e* evaluations.
Scores stay at recorded values during a display transition.
The larger canvas retains the same dimensions across frames; the duplex moves
vertically as the number of forward- and reverse-strand matches changes.

The sampled curve cannot recover the time or sequence
of every intermediate improvement, and playback speed is a presentation choice,
not elapsed optimization time. Sparse observations should not be described as
a complete trajectory.

## Use Python

After saving an observation as described in the
[observation reference](search-observations.md):

```python
# Import the models and operations used in this example.
from pathlib import Path
from motif_balance.playback import inspect_playback, render_playback_html

# Verify the saved states and construct the playback frames.
playback = inspect_playback(Path("observation.json").read_bytes())
# Save a new HTML player that displays four recorded states per second.
with Path("playback.html").open("xb") as output:
    output.write(render_playback_html(playback, fps=4))
```

This example assumes a trusted local file. Integrations accepting external files
should bound reads before loading bytes; the CLI does this automatically.
`inspect_playback` verifies the supplied observation and constructs at most 256
combined frame records. Chain views use only snapshots that actually recorded
that chain, rather than substituting incumbent-only checkpoints.
Render functions consume that data without rerunning optimization themselves.

To show ongoing exploration behind the best sequence, use `--search-chain all`
with `animate`, or pass `search_chain_id="all"` to `inspect_playback` in Python.
This displays each recorded chain separately in faint gray. Use `0` through `7`
to select one fixed chain instead. The colored molecule and curve retain the best result. It cannot
be combined with `chain_id`. The eight chains share one run's budget; they are
not eight independent repeated searches. A checkpoint without a new chain state
keeps the preceding recorded gray state at its original evaluation coordinate.
No state is shown before it was recorded. The gray curve is not every evaluated
proposal, and its hard-minimum balance differs from the smooth acceptance score.

The twelve-model example ends its movie at the first recorded final-best score,
using `view.until_last_improvement()` or `--until-last-improvement`. This selects
an unchanged prefix and rescales the evaluation axis to its endpoint. It does not
identify the exact discovery time between observations or change the full run's
budget. The HTML overview selects eight best-sequence frames. Gray placements can
change while the best sequence remains fixed. A best-scoring proposal need not
be adopted by a chain, and snapshots do not include every evaluated proposal.

The current projection is `playback-inspection/v2`. Earlier saved projections
remain bound to their producing version. Recreate them from the unchanged search
observation with `inspect_playback`; there is no automatic projection conversion.


## Export media

HTML and SVG use the base installation. PNG, GIF and MP4 additionally require
the `visualization` extra:

```bash
# Install the optional image and video export dependencies.
python -m pip install 'motif-balance[visualization]'
# Encode the recorded states as an MP4 video.
motif-balance animate observation.json --format mp4 --out playback.mp4
```

Use `--fps` to set 1–30 frames per second. PNG accepts `--frame`; GIF and MP4
show the recorded frame sequence.

For smooth movement between saved states:

```bash
motif-balance animate observation.json --format mp4 --out smooth.mp4 \
  --search-chain all --until-last-improvement \
  --fps 30 --transition-frames 26 --pacing accelerating --width 1400
```

`--transition-frames` adds 0–30 display frames between consecutive observations.
With `--pacing accelerating`, this is the opening transition length; subsequent
transitions decrease gradually to one fifth of it. The default pacing is uniform.
Motif drawings move and crossfade, rotating when their selected strand changes.
DNA letters and scores come from the two recorded endpoints. Transition frames
retain the earlier point on the recovery curve until the next observation is
reached. Each saved state occupies one frame, without an added pause or
slowdown at every checkpoint. Tweened movies skip unchanged intermediate drawings;
the curve and HTML player retain every observation, and the final checkpoint is
always shown. Display transitions do not represent additional evaluated sequences.
`--width` reduces raster size while preserving the aspect ratio. MP4 streams
frames to the encoder; GIF holds them in memory and enforces a pixel limit.

Keep the observation record and source-model attribution with shared media.
The export is an explanation of that run, not a replacement for its sequence
and scoring records.

Media export also limits total encoded-frame work to one billion pixels before
rasterization or encoder startup. MP4 streams frames to bound memory, but is
subject to this total-work limit. Reduce width, snapshots, or transition frames
when an export is refused.
