"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/playback/render.py

Compose equal square panels for recorded recovery and its verified DNA state.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

import math

from motif_balance.errors import ArtifactError

from .duplex import CELL, LANE, label, left_margin, render_duplex
from .model import PlaybackInspection

# Logical coordinates are shared by SVG, HTML and high-resolution media.
PANEL = 520
LEFT = 80
RIGHT = 640
TOP = 66
SCALE = 1.6
WIDTH = 1200
HEIGHT = 660


def frame_dimensions(view: PlaybackInspection) -> tuple[int, int, int]:
    forward = max(sum(m.strand == "+" for m in f.candidate.matches) for f in view.frames)
    return round(WIDTH * SCALE), round(HEIGHT * SCALE), forward


def validate_view(view: PlaybackInspection) -> PlaybackInspection:
    if not isinstance(view, PlaybackInspection):
        raise ArtifactError("rendering requires an inspected playback")
    checked = PlaybackInspection.model_validate(view.model_dump(mode="python"))
    if checked.problem.length > 128 or len(checked.problem.motifs) > 8:
        raise ArtifactError("compact playback supports at most 128 bases and eight motifs")
    return checked


def render_playback_svg(view: PlaybackInspection, *, frame: int = -1) -> bytes:
    """Draw a saved state; the curve connects observations, not every proposal."""
    view = validate_view(view)
    if type(frame) is not int or not -len(view.frames) <= frame < len(view.frames):
        raise ArtifactError("frame is outside the recorded playback")
    index = frame % len(view.frames)
    current = view.frames[index]
    width, height, top_lanes = frame_dimensions(view)
    reverse = max(sum(m.strand == "-" for m in f.candidate.matches) for f in view.frames)
    molecule_width = left_margin(view.problem) + view.problem.length * CELL + 100
    molecule_height = 110 + (top_lanes + reverse) * LANE
    zoom = min((PANEL - 20) / molecule_width, (PANEL - 20) / molecule_height)
    molecule_x = RIGHT + (PANEL - molecule_width * zoom) / 2
    molecule_y = TOP + (PANEL - molecule_height * zoom) / 2
    scope = "Motif preferences share one sequence"
    if view.chain_id is not None:
        scope = "Search explores alternative sequences"
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'data-evaluations="{current.evaluations}" '
        f'data-observation-sha256="{view.observation_sha256}" '
        'role="img" aria-labelledby="title desc">',
        '<title id="title">Recorded search and motif matches</title>',
        f'<desc id="desc">Saved observation at {current.evaluations} candidate evaluations. '
        "The orange point identifies the DNA shown at right. The blue curve connects "
        "sampled best scores; intermediate improvements are not recorded here. "
        "Logos show 0 to 2 bits, with the matched nucleotide colored. "
        "DNA gray saturation reports the largest relative matched-base probability. </desc>",
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="white"/>',
        label(LEFT + PANEL / 2, 35, "Search improves the weakest match", anchor="middle"),
        label(RIGHT + PANEL / 2, 35, scope, anchor="middle"),
    ]
    for name, panel_x in (("recovery", LEFT), ("molecule", RIGHT)):
        parts.append(
            f'<rect data-panel="{name}" x="{panel_x}" y="{TOP}" '
            f'width="{PANEL}" height="{PANEL}" fill="white"/>'
        )
    x0, x1, y0, y1 = LEFT, LEFT + PANEL, TOP, TOP + PANEL
    max_log = math.log10(max(2, view.frames[-1].evaluations))

    def x_position(evaluations: int) -> float:
        return x0 + PANEL * math.log10(evaluations) / max_log

    def y_position(score: float) -> float:
        # Small fixed headroom keeps endpoint markers clear of the spines.
        return y1 - PANEL * (score + 0.025) / 1.05

    # Grid precedes every data mark. Only bottom and left spines are drawn.
    for value in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = y_position(value)
        parts.append(f'<path d="M{x0} {y:g} H{x1}" stroke="#E3E5E8" stroke-width="1.2"/>')
        parts.append(f'<path d="M{x0 - 6} {y:g} H{x0}" stroke="#444" stroke-width="1.8"/>')
        parts.append(label(x0 - 12, y + 6, f"{value:g}", anchor="end"))
    tick = 1
    while tick <= view.frames[-1].evaluations:
        x = x_position(tick)
        parts.append(f'<path d="M{x:g} {y0} V{y1}" stroke="#E3E5E8" stroke-width="1.2"/>')
        parts.append(f'<path d="M{x:g} {y1} v6" stroke="#444" stroke-width="1.8"/>')
        parts.append(label(x, y1 + 28, f"{tick:,}", anchor="middle"))
        tick *= 10
    parts.append(f'<path d="M{x0} {y0} V{y1} H{x1}" stroke="#444" stroke-width="1.8" fill="none"/>')
    parts.append(
        label((x0 + x1) / 2, y1 + 61, "Candidate evaluations (log scale)", anchor="middle")
    )
    parts.append(
        f'<g transform="translate(30 {(y0 + y1) / 2}) rotate(-90)">'
        + label(
            0, 0, "Best balance recovered" if view.chain_id is None else "Balance", anchor="middle"
        )
        + "</g>"
    )
    xy = [(x_position(f.evaluations), y_position(f.best_balance)) for f in view.frames]
    if len(xy) > 1:
        points = " ".join(f"{x:.3f},{y:.3f}" for x, y in xy[: index + 1])
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="#0072B2" '
            'stroke-width="3" stroke-linejoin="round"/>'
        )
    x, y = x_position(current.evaluations), y_position(current.candidate.balance_score)
    parts.append(
        f'<circle data-current-state="true" data-score="{current.candidate.balance_score}" '
        f'data-evaluations="{current.evaluations}" cx="{x:.3f}" cy="{y:.3f}" '
        'r="6" fill="#D55E00" stroke="white" stroke-width="1.5"/>'
    )
    parts.append(
        f'<g data-duplex-layout="fixed" transform="translate({molecule_x:g} '
        f'{molecule_y:g}) scale({zoom:g})">'
    )
    parts.append(
        render_duplex(
            view.problem,
            current.candidate,
            top_lanes=top_lanes,
        )
    )
    return "".join([*parts, "</g></svg>\n"]).encode()
