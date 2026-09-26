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
from xml.etree import ElementTree as ET

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
    candidates = [
        c for f in view.frames for c in (f.candidate, f.search_candidate) if c is not None
    ]
    forward = max(sum(m.strand == "+" for m in c.matches) for c in candidates)
    reverse = max(sum(m.strand == "-" for m in c.matches) for c in candidates)
    molecule_width = left_margin(view.problem) + view.problem.length * CELL + 100
    molecule_height = 110 + (forward + reverse) * LANE
    if len(view.problem.motifs) > 8:
        chart_size = 1000
        recovery_x = LEFT + 110
        molecule_x = recovery_x + chart_size + 150
        width = molecule_x + molecule_width + 40
        molecule_height = 110 + len(view.problem.motifs) * LANE
        return {
            "width": width,
            "height": 170 + molecule_height + 40,
            "recovery_x": recovery_x,
            "recovery_y": 170 + (molecule_height - chart_size) / 2,
            "chart_size": chart_size,
            "molecule_x": molecule_x,
            "molecule_y": 170,
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
    font = 54 if expanded else 18
    tick_font = 44 if expanded else 18
    canvas_width, canvas_height = geometry["width"], geometry["height"]
    molecule_x, molecule_y, zoom = geometry["molecule_x"], geometry["molecule_y"], geometry["zoom"]
    recovery_x, recovery_y = geometry["recovery_x"], geometry["recovery_y"]
    scope = "Best DNA found"
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
        "DNA gray saturation reports the largest relative matched-base probability. "
        "When present, the faint gray layer shows recorded states of one fixed search chain, "
        "not all proposals or an interpolated sequence. </desc>",
        f'<rect width="{canvas_width:g}" height="{canvas_height:g}" fill="white"/>',
        label(
            recovery_x + panel / 2,
            66 if expanded else recovery_y - 31,
            "Search progress" if view.search_chain_id is not None else "Best balance so far",
            anchor="middle",
            size=72 if expanded else font,
        ),
        label(
            molecule_x + geometry["molecule_width"] / 2 if expanded else RIGHT + PANEL / 2,
            66 if expanded else 35,
            scope,
            anchor="middle",
            size=72 if expanded else font,
        ),
    ]
    if expanded:
        # Definitions use distinct mathematical objects, as in the manuscript.
        parts.append(
            f'<text x="{recovery_x + panel / 2:g}" y="128" font-family="Arial,sans-serif" '
            'font-size="46" text-anchor="middle" fill="#454C4B">'
            '<tspan font-style="italic">B</tspan>(<tspan font-style="italic">s</tspan>) = min'
            '<tspan baseline-shift="sub" font-size="30" font-style="italic">i</tspan> '
            '<tspan font-style="italic">q</tspan>'
            '<tspan baseline-shift="sub" font-size="30" font-style="italic">i</tspan>'
            '(<tspan font-style="italic">s</tspan>)</text>'
        )
        parts.append(
            f'<text x="{molecule_x + geometry["molecule_width"] / 2:g}" y="128" '
            'font-family="Arial,sans-serif" font-size="40" text-anchor="middle" fill="#454C4B">'
            '<tspan font-style="italic">q</tspan>'
            '<tspan baseline-shift="sub" font-size="26" font-style="italic">i</tspan>'
            ' = normalized best match for motif <tspan font-style="italic">i</tspan></text>'
        )
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
        # Headroom leaves space for the score label above a balance-one endpoint.
        return y1 - panel * (score + 0.025) / 1.125

    # Grid precedes every data mark. Only bottom and left spines are drawn.
    for value in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = y_position(value)
        parts.append(f'<path d="M{x0} {y:g} H{x1}" stroke="#E3E5E8" stroke-width="1.2"/>')
        parts.append(f'<path d="M{x0 - 6} {y:g} H{x0}" stroke="#444" stroke-width="1.8"/>')
        parts.append(
            label(x0 - 16, y + (13 if expanded else 6), f"{value:g}", anchor="end", size=tick_font)
        )
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
            label(x, y1 + (50 if expanded else 28), f"{tick:,}", anchor="middle", size=tick_font)
        )
    parts.append(f'<path d="M{x0} {y0} V{y1} H{x1}" stroke="#444" stroke-width="1.8" fill="none"/>')
    parts.append(
        label(
            (x0 + x1) / 2,
            y1 + (110 if expanded else 61),
            "DNA candidates evaluated, e" if expanded else "Candidate evaluations (log scale)",
            anchor="middle",
            size=font,
        ).replace(", e</text>", ', <tspan font-style="italic">e</tspan></text>')
    )
    if expanded:
        parts.append(label((x0 + x1) / 2, y1 + 164, "Logarithmic scale", anchor="middle", size=40))
    parts.append(
        f'<g transform="translate({x0 - (128 if expanded else 50):g} {(y0 + y1) / 2}) rotate(-90)">'
        + label(
            0,
            0,
            ("Weakest motif score, B(s)" if expanded else "Best balance recovered")
            if view.chain_id is None
            else "Balance",
            anchor="middle",
            size=font,
        ).replace(
            "B(s)", '<tspan font-style="italic">B</tspan>(<tspan font-style="italic">s</tspan>)'
        )
        + "</g>"
    )
    if view.search_chain_id is not None:
        seen = {}
        for f in view.frames[: index + 1]:
            if f.search_candidate is not None:
                assert f.search_evaluations is not None
                seen[f.search_evaluations] = f.search_candidate.balance_score
        if seen:
            points = " ".join(f"{x_position(e):.3f},{y_position(b):.3f}" for e, b in seen.items())
            parts.append(
                f'<polyline data-search-trace="true" points="{points}" fill="none" '
                'stroke="#A4ADAA" stroke-width="2.5"/>'
            )
        if current.search_candidate is not None:
            assert current.search_evaluations is not None
            sx, sy = (
                x_position(current.search_evaluations),
                y_position(current.search_candidate.balance_score),
            )
            parts.append(
                '<circle data-search-state="true" '
                f'data-score="{current.search_candidate.balance_score}" '
                f'data-evaluations="{current.search_evaluations}" '
                f'cx="{sx:.3f}" cy="{sy:.3f}" r="9" fill="#929B98"/>'
            )
        for j, (color, text) in enumerate(
            (("#0072B2", "Best so far"), ("#929B98", "Current sequence B(s)"))
        ):
            ly = y1 - (130 if expanded else 70) + j * (62 if expanded else 30)
            parts.append(f'<path d="M{x0 + 32:g} {ly:g} h42" stroke="{color}" stroke-width="5"/>')
            parts.append(
                label(x0 + 92, ly + (14 if expanded else 6), text, size=44 if expanded else 18)
            )
    xy = [(x_position(f.evaluations), y_position(f.best_balance)) for f in view.frames]
    if len(xy) > 1:
        points = " ".join(f"{x:.3f},{y:.3f}" for x, y in xy[: index + 1])
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="#0072B2" '
            f'stroke-width="{5 if expanded else 3}" stroke-linejoin="round"/>'
        )
    x, y = x_position(current.evaluations), y_position(current.candidate.balance_score)
    parts.append(
        f'<circle data-current-state="true" data-score="{current.candidate.balance_score}" '
        f'data-evaluations="{current.evaluations}" cx="{x:.3f}" cy="{y:.3f}" '
        f'r="{8 if expanded else 6}" fill="#D55E00" stroke="white" stroke-width="1.5"/>'
    )
    score_anchor = "end" if x > (x0 + x1) / 2 else "start"
    parts.append(
        f'<text data-current-score="{current.candidate.balance_score}" '
        f'x="{x:.3f}" y="{y - (36 if expanded else 22):.3f}" '
        f'font-family="Arial,sans-serif" font-size="{64 if expanded else 24}" '
        f'font-weight="600" text-anchor="{score_anchor}" fill="#252525">'
        '<tspan font-style="italic">B</tspan>'
        + (
            '<tspan baseline-shift="sub" font-size="65%">best</tspan>'
            '(<tspan font-style="italic">e</tspan>)'
            if view.chain_id is None
            else ""
        )
        + f" = {current.candidate.balance_score:.3f}</text>"
    )
    if current.search_candidate is not None:
        ghost = ET.fromstring(
            "<g>"
            + render_duplex(
                view.problem,
                current.search_candidate,
                top_lanes=(
                    sum(m.strand == "+" for m in current.search_candidate.matches)
                    if expanded
                    else top_lanes
                ),
            )
            + "</g>"
        )
        for parent in list(ghost.iter()):
            for child in list(parent):
                if (
                    parent.get("data-motif-id")
                    and child.tag == "text"
                    and child.get("fill") != "#FFFFFF"
                ):
                    parent.remove(child)
            identifier = parent.get("id")
            if identifier:
                parent.set("id", "search-" + identifier)
            if parent.get("fill") and parent.get("fill") not in ("none", "#FFFFFF"):
                parent.set("fill", "#76847F")
        parts.append(
            f'<g data-duplex-layout="search" opacity="0.16" '
            f'transform="translate({molecule_x:g} {molecule_y:g}) scale({zoom:g})">'
        )
        parts.extend(ET.tostring(n, encoding="unicode") for n in ghost)
        parts.append("</g>")
    parts.append(
        f'<g data-duplex-layout="best" transform="translate({molecule_x:g} '
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
