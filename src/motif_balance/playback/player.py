"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/playback/player.py

Provide local, accessible controls for recorded SVG search frames.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

import json
from string import Template

from motif_balance.errors import ArtifactError

from .model import PlaybackInspection
from .render import render_playback_svg, validate_view

_PAGE = Template("""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Motif search playback</title><style>
body{margin:16px;font:18px Arial,sans-serif;color:#252525;background:white}
main{max-width:1500px;margin:auto}svg{width:100%;height:auto;display:block}
.controls{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
button{font:inherit;background:white;border:1px solid #777;border-radius:5px;padding:7px 18px}
input{flex:1;min-width:200px}p{font-size:16px;color:#555;line-height:1.5}
</style><main><div id="screen">$first_frame</div><div class="controls">
<button id="play" type="button" aria-pressed="false">Play</button>
<label for="frame">Observation</label>
<input id="frame" type="range" min="0" max="$last" value="0" step="1">
<output id="position">1 / $count</output></div>
<p>The blue curve joins sampled best scores. The orange point identifies the DNA shown.
Unequal horizontal spacing reflects the recorded evaluation counts on a logarithmic axis.
Each molecular view is a recorded sequence,
rescored under the supplied models and strand policy. Frame timing is for viewing
and does not represent elapsed search time. Use the slider to inspect changes in
position, orientation and overlap.</p></main>
<script type="application/json" id="frames">$frames</script>
<script>
"use strict";
const frames=JSON.parse(document.getElementById("frames").textContent);
const slider=document.getElementById("frame"), button=document.getElementById("play");
let timer=null;
function show(){
  document.getElementById("screen").innerHTML=frames[Number(slider.value)];
  document.getElementById("position").textContent=(Number(slider.value)+1)+" / "+frames.length;
}
function stop(){
  clearInterval(timer);timer=null;button.textContent="Play";
  button.setAttribute("aria-pressed","false");
}
slider.addEventListener("input",()=>{stop();show();});
button.addEventListener("click",()=>{
  if(timer){stop();return;}
  if(Number(slider.value)===frames.length-1){slider.value=0;show();}
  button.textContent="Pause";button.setAttribute("aria-pressed","true");
  timer=setInterval(()=>{
    if(Number(slider.value)>=frames.length-1){stop();return;}
    slider.value=Number(slider.value)+1;show();
  },$interval);
});
document.addEventListener("visibilitychange",()=>{if(document.hidden)stop();});
matchMedia("(prefers-reduced-motion: reduce)").addEventListener("change",stop);
</script></html>
""")


def render_playback_html(view: PlaybackInspection, *, fps: int = 4) -> bytes:
    """Return a self-contained player with no network, autoplay or interpolated states."""
    view = validate_view(view)
    if type(fps) is not int or not 1 <= fps <= 30:
        raise ArtifactError("fps must be an integer from 1 through 30")
    glyph_count = sum(motif.width for motif in view.problem.motifs) * 4 * len(view.frames)
    if glyph_count * 1800 > 32 * 1024 * 1024:
        raise ArtifactError("projected playback HTML exceeds 32 MiB; request fewer snapshots")
    frames = [render_playback_svg(view, frame=i).decode() for i in range(len(view.frames))]
    # Escape '<' so motif identifiers cannot terminate the JSON script element.
    serialized = json.dumps(frames, ensure_ascii=True).replace("<", "\\u003c")
    result = _PAGE.substitute(
        first_frame=frames[0],
        last=len(frames) - 1,
        count=len(frames),
        frames=serialized,
        interval=round(1000 / fps),
    ).encode()
    if len(result) > 32 * 1024 * 1024:
        raise ArtifactError("playback HTML exceeds 32 MiB; request fewer snapshots")
    return result
