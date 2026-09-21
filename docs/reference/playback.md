---
doc_id: motif-balance-playback
title: Show a recorded search
intent: Render recorded sequence states alongside best observed scores.
audience: [users]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-21
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
snapshot. `--chain 0` instead follows one fixed, zero-based search-chain identity;
its current score can decrease. The best-so-far curve remains separate from that
current state. Uniform random sampling and complete enumeration have no search
chains. Missing chains or unsupported frames are rejected.

The blue curve connects recorded snapshots. The orange point gives the score
and evaluation count for the displayed DNA. Unequal spacing comes from the
recorded counts on a logarithmic axis. Each snapshot receives equal viewing time.
Both subpanels have the same square content area, with a duplex scale and motif
DNA baselines fixed across the recording. The export is 1,920 × 1,056 pixels.

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
`inspect_playback` verifies the supplied observation and constructs frame data.
Render functions consume that data without rerunning optimization themselves.

## Export media

HTML and SVG use the base installation. PNG, GIF and MP4 additionally require
the `visualization` extra:

```bash
# Install the optional image and video export dependencies.
uv sync --locked --extra visualization
# Encode the recorded states as an MP4 video.
uv run motif-balance animate observation.json --format mp4 --out playback.mp4
```

Use `--fps` to set 1–30 frames per second. PNG accepts `--frame`; GIF and MP4
show the recorded frame sequence. Source-checkout installation is shown here;
when installing a wheel, request its `[visualization]` extra instead.

Keep the observation record and source-model attribution with shared media.
The export is an explanation of that run, not a replacement for its sequence
and scoring records.
