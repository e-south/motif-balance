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
continuous molecular view, with larger axis labels.
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
  --fps 20 --transition-frames 16 --width 1400
```

`--transition-frames` adds 0–30 display frames between consecutive observations.
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
