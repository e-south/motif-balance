"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/playback/render.py

Compose recorded recovery and its verified, strand-aligned DNA state.

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


def _layout(view: PlaybackInspection) -> dict[str, float]:
    forward = max(sum(m.strand == "+" for m in f.candidate.matches) for f in view.frames)
    reverse = max(sum(m.strand == "-" for m in f.candidate.matches) for f in view.frames)
    molecule_width = left_margin(view.problem) + view.problem.length * CELL + 100
    molecule_height = 110 + (forward + reverse) * LANE
    if len(view.problem.motifs) > 8:
        chart_size = 800
        recovery_x = LEFT + 30
        molecule_x = recovery_x + chart_size + 110
        width = molecule_x + molecule_width + 40
        molecule_height = 110 + len(view.problem.motifs) * LANE
        return {
            "width": width,
            "height": TOP + molecule_height + 40,
            "recovery_x": recovery_x,
            "recovery_y": TOP + (molecule_height - chart_size) / 2,
            "chart_size": chart_size,
            "molecule_x": molecule_x,
            "molecule_y": TOP,
            "molecule_width": molecule_width,
            "molecule_height": molecule_height,
            "zoom": 1,
            "forward": forward,
        }
    zoom = min((PANEL - 20) / molecule_width, (PANEL - 20) / molecule_height)
    return {
        "width": WIDTH,
        "height": HEIGHT,
        "recovery_x": LEFT,
        "recovery_y": TOP,
        "chart_size": PANEL,
        "molecule_x": RIGHT + (PANEL - molecule_width * zoom) / 2,
        "molecule_y": TOP + (PANEL - molecule_height * zoom) / 2,
        "molecule_width": PANEL,
        "molecule_height": PANEL,
        "zoom": zoom,
        "forward": forward,
    }


def frame_dimensions(view: PlaybackInspection) -> tuple[int, int, int]:
    geometry = _layout(view)
    return (
        round(geometry["width"] * SCALE),
        round(geometry["height"] * SCALE),
        int(geometry["forward"]),
    )


def validate_view(view: PlaybackInspection) -> PlaybackInspection:
    if not isinstance(view, PlaybackInspection):
        raise ArtifactError("rendering requires an inspected playback")
    checked = PlaybackInspection.model_validate(view.model_dump(mode="python"))
    if checked.problem.length > 128 or len(checked.problem.motifs) > 12:
        raise ArtifactError("playback supports at most 128 bases and twelve motifs")
    return checked


def render_playback_svg(view: PlaybackInspection, *, frame: int = -1) -> bytes:
    """Draw a saved state; the curve connects observations, not every proposal."""
    view = validate_view(view)
    if type(frame) is not int or not -len(view.frames) <= frame < len(view.frames):
        raise ArtifactError("frame is outside the recorded playback")
    index = frame % len(view.frames)
    current = view.frames[index]
    width, height, top_lanes = frame_dimensions(view)
    geometry = _layout(view)
    expanded = len(view.problem.motifs) > 8
    panel = geometry["chart_size"]
    font = 26 if expanded else 18
    canvas_width, canvas_height = geometry["width"], geometry["height"]
    molecule_x, molecule_y, zoom = geometry["molecule_x"], geometry["molecule_y"], geometry["zoom"]
    recovery_x, recovery_y = geometry["recovery_x"], geometry["recovery_y"]
    scope = "Motif preferences share one sequence"
    if view.chain_id is not None:
        scope = "Search explores alternative sequences"
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {canvas_width:g} {canvas_height:g}" '
        f'data-evaluations="{current.evaluations}" '
        f'data-observation-sha256="{view.observation_sha256}" '
        'role="img" aria-labelledby="title desc">',
        '<title id="title">Recorded search and motif matches</title>',
        f'<desc id="desc">Saved observation at {current.evaluations} candidate evaluations. '
        "The orange point identifies the displayed DNA. The blue curve connects "
        "sampled best scores; intermediate improvements are not recorded here. "
        "Logos show 0 to 2 bits, with the matched nucleotide colored. "
        "DNA gray saturation reports the largest relative matched-base probability. </desc>",
        f'<rect width="{canvas_width:g}" height="{canvas_height:g}" fill="white"/>',
        label(
            recovery_x + panel / 2,
            recovery_y - 38,
            "Best balance so far",
            anchor="middle",
            size=font + 2 if expanded else font,
        ),
        label(
            molecule_x + geometry["molecule_width"] / 2 if expanded else RIGHT + PANEL / 2,
            35,
            scope,
            anchor="middle",
            size=font + 2 if expanded else font,
        ),
    ]
    panels: list[tuple[str, float, float, float, float]] = [
        ("recovery", recovery_x, recovery_y, panel, panel)
    ]
    panels.append(
        (
            "molecule",
            molecule_x if expanded else RIGHT,
            molecule_y if expanded else TOP,
            geometry["molecule_width"],
            geometry["molecule_height"],
        )
    )
    for name, panel_x, panel_y, panel_width, panel_height in panels:
        parts.append(
            f'<rect data-panel="{name}" x="{panel_x:g}" y="{panel_y:g}" '
            f'width="{panel_width:g}" height="{panel_height:g}" fill="white"/>'
        )
    x0, x1, y0, y1 = recovery_x, recovery_x + panel, recovery_y, recovery_y + panel
    max_log = math.log10(max(2, view.frames[-1].evaluations))

    def x_position(evaluations: int) -> float:
        return x0 + panel * math.log10(evaluations) / max_log

    def y_position(score: float) -> float:
        # Small fixed headroom keeps endpoint markers clear of the spines.
        return y1 - panel * (score + 0.025) / 1.05

    # Grid precedes every data mark. Only bottom and left spines are drawn.
    for value in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = y_position(value)
        parts.append(f'<path d="M{x0} {y:g} H{x1}" stroke="#E3E5E8" stroke-width="1.2"/>')
        parts.append(f'<path d="M{x0 - 6} {y:g} H{x0}" stroke="#444" stroke-width="1.8"/>')
        parts.append(label(x0 - 12, y + 6, f"{value:g}", anchor="end", size=font))
    last_evaluation = view.frames[-1].evaluations
    ticks = [1]
    tick = 10
    while tick <= last_evaluation / 2:
        ticks.append(tick)
        tick *= 10
    if last_evaluation > 1:
        ticks.append(last_evaluation)
    for tick in ticks:
        x = x_position(tick)
        parts.append(f'<path d="M{x:g} {y0} V{y1}" stroke="#E3E5E8" stroke-width="1.2"/>')
        parts.append(f'<path d="M{x:g} {y1} v6" stroke="#444" stroke-width="1.8"/>')
        parts.append(
            label(x, y1 + (36 if expanded else 28), f"{tick:,}", anchor="middle", size=font)
        )
    parts.append(f'<path d="M{x0} {y0} V{y1} H{x1}" stroke="#444" stroke-width="1.8" fill="none"/>')
    parts.append(
        label(
            (x0 + x1) / 2,
            y1 + (78 if expanded else 61),
            "Candidate evaluations (log scale)",
            anchor="middle",
            size=font,
        )
    )
    parts.append(
        f'<g transform="translate({x0 - (58 if expanded else 50):g} {(y0 + y1) / 2}) rotate(-90)">'
        + label(
            0,
            0,
            "Best balance recovered" if view.chain_id is None else "Balance",
            anchor="middle",
            size=font,
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
        f'r="{8 if expanded else 6}" fill="#D55E00" stroke="white" stroke-width="1.5"/>'
    )
    parts.append(
        f'<g data-duplex-layout="fixed" transform="translate({molecule_x:g} '
        f'{molecule_y:g}) scale({zoom:g})">'
    )
    parts.append(
        render_duplex(
            view.problem,
            current.candidate,
            top_lanes=(
                sum(m.strand == "+" for m in current.candidate.matches) if expanded else top_lanes
            ),
        )
    )
    return "".join([*parts, "</g></svg>\n"]).encode()
