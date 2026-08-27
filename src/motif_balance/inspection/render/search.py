from __future__ import annotations

from typing import Literal

from ..limits import MAX_SVG_CHECKPOINTS
from ..model import ResultInspection
from .svg_primitives import ACCENT, INK, MUTED, PAPER, finish_svg, svg_start, text


def _shown(
    inspection: ResultInspection,
) -> tuple[tuple[tuple[int, float], ...], Literal["exact_step", "sampled_markers"]]:
    checkpoints = inspection.search.checkpoints
    if len(checkpoints) <= MAX_SVG_CHECKPOINTS:
        return (
            tuple((item.evaluations, item.best_score) for item in checkpoints),
            "exact_step",
        )
    changes = {
        index
        for index in range(1, len(checkpoints))
        if checkpoints[index].best_score > checkpoints[index - 1].best_score + 1.0e-12
    }
    essential = {0, len(checkpoints) - 1}
    for index in changes:
        essential.update((index - 1, index))
    if len(essential) <= MAX_SVG_CHECKPOINTS:
        return (
            tuple(
                (checkpoints[index].evaluations, checkpoints[index].best_score)
                for index in sorted(essential)
            ),
            "exact_step",
        )
    last = len(checkpoints) - 1
    indices = tuple(
        sorted(
            {
                round(index * last / (MAX_SVG_CHECKPOINTS - 1))
                for index in range(MAX_SVG_CHECKPOINTS)
            }
        )
    )
    return (
        tuple((checkpoints[index].evaluations, checkpoints[index].best_score) for index in indices),
        "sampled_markers",
    )


def render_search_svg(inspection: ResultInspection) -> bytes | None:
    """Render the running maximum of recorded hard balance scores."""

    if not inspection.search.checkpoints:
        return None
    shown, display_mode = _shown(inspection)
    total = len(inspection.search.checkpoints)
    width = 960
    height = 350
    left, right, top, bottom = 88, 36, 82, 72
    plot_width = width - left - right
    plot_height = height - top - bottom
    x_max = inspection.search.evaluator_calls
    y_max = max(1.0e-12, max(score for _, score in shown))

    def x(value: int) -> float:
        return left + plot_width * value / x_max

    def y(value: float) -> float:
        return top + plot_height * (y_max - value) / y_max

    parts = svg_start(
        width=width,
        height=height,
        title_id="search-record-title",
        desc_id="search-record-desc",
        view_id="search-record-view",
    )
    parts.extend(
        [
            '<title id="search-record-title">Recorded best observed balance score</title>',
            '<desc id="search-record-desc">Running maximum of the published hard minimum '
            "balance score at recorded evaluator calls. This is not accepted-state history, "
            "literal hill climbing, chain dynamics, convergence evidence, or a "
            "global-optimality claim.</desc>",
            f'<rect width="{width}" height="{height}" fill="{PAPER}"/>',
            '<g id="search-record">',
            text(20, 30, "Search record", size=18, weight=650),
            text(
                20,
                54,
                f"running maximum · {len(shown)} of {total} recorded checkpoints · "
                + (
                    "exact recorded step boundaries · "
                    if display_mode == "exact_step"
                    else "sampled markers; omitted intervals are not connected · "
                )
                + f"stop: {inspection.search.stop_reason}",
                size=13,
                fill=MUTED,
            ),
            f'<line x1="{left}" y1="{top + plot_height}" '
            f'x2="{left + plot_width}" y2="{top + plot_height}" stroke="{INK}"/>',
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="{INK}"/>',
            text(
                left + plot_width / 2,
                height - 24,
                "Evaluator calls",
                size=12,
                anchor="middle",
                weight=650,
            ),
            text(18, top - 12, "Best observed balance_score", size=12, weight=650),
            text(left - 10, top + plot_height + 4, "0", size=10, anchor="end", fill=MUTED),
            text(left - 10, top + 4, f"{y_max:.6g}", size=10, anchor="end", fill=MUTED),
            text(left, top + plot_height + 20, "0", size=10, anchor="middle", fill=MUTED),
            text(
                left + plot_width,
                top + plot_height + 20,
                x_max,
                size=10,
                anchor="middle",
                fill=MUTED,
            ),
        ]
    )
    if display_mode == "exact_step":
        points: list[tuple[float, float]] = []
        for evaluations, best_score in shown:
            current = (x(evaluations), y(best_score))
            if points:
                points.append((current[0], points[-1][1]))
            points.append(current)
        path = " ".join(
            ("M" if index == 0 else "L") + f" {px:.3f} {py:.3f}"
            for index, (px, py) in enumerate(points)
        )
        parts.append(
            f'<path id="best-observed-step" d="{path}" fill="none" '
            f'stroke="{ACCENT}" stroke-width="3" data-display-mode="exact-step" '
            f'data-checkpoint-count="{total}" data-displayed-checkpoints="{len(shown)}"/>'
        )
    else:
        parts.extend(
            [
                f'<g id="sampled-checkpoints" data-display-mode="sampled-markers" '
                f'data-checkpoint-count="{total}" data-displayed-checkpoints="{len(shown)}">',
                *(
                    f'<circle cx="{x(evaluations):.3f}" cy="{y(best_score):.3f}" '
                    f'r="2" fill="{ACCENT}"/>'
                    for evaluations, best_score in shown
                ),
                "</g>",
            ]
        )
    parts.extend(
        [
            f'<circle cx="{x(shown[-1][0]):.3f}" cy="{y(shown[-1][1]):.3f}" '
            f'r="4" fill="{ACCENT}" stroke="{INK}"/>',
            text(
                left + plot_width,
                y(shown[-1][1]) - 10,
                f"best observed {shown[-1][1]:.6g}",
                size=11,
                anchor="end",
            ),
            text(
                left,
                height - 4,
                f"Stopped after {inspection.search.evaluator_calls} evaluator calls: "
                f"{inspection.search.stop_reason}. No convergence or global optimality is implied.",
                size=11,
                fill=MUTED,
            ),
            "</g>",
            "</svg>",
        ]
    )
    return finish_svg(parts)
