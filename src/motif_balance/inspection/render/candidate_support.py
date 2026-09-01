from __future__ import annotations

from ..model import InspectionCandidate
from .candidate_layout import CandidateLayout, support_label
from .svg_primitives import INK, MUTED, NEGATIVE, POSITIVE, motif_color, motif_id, text


def render_position_support(
    candidate: InspectionCandidate,
    layout: CandidateLayout,
) -> list[str]:
    """Render signed observed-base support from the verified projection."""

    parts = [
        f'<g id="position-support" data-cell-width="{layout.cell}">',
        text(
            20,
            layout.support_y - 12,
            "Observed-base positional support (raw LLR contributions)",
            size=12,
            weight=650,
        ),
    ]
    for row, match in enumerate(layout.shown):
        y = layout.support_y + row * 40
        color = motif_color(match.motif_id)
        parts.append(
            f'<g class="position-support-row" data-motif-id="{motif_id(match.motif_id)}" '
            f'data-motif-color="{color}">'
        )
        parts.append(
            text(
                20,
                y + 17,
                f"{match.motif_id} {match.strand} · raw {match.raw_score:.4g}",
                size=12,
                family="ui-monospace,monospace",
            )
        )
        parts.append(
            f'<line x1="{layout.left}" y1="{y + 12}" '
            f'x2="{layout.left + len(candidate.sequence) * layout.cell}" '
            f'y2="{y + 12}" stroke="{color}" stroke-width="1.5"/>'
        )
        for support in match.position_support:
            x = layout.left + support.candidate_position * layout.cell
            intensity = min(0.85, 0.18 + abs(support.llr_contribution) / 5)
            fill = POSITIVE if support.llr_contribution >= 0 else NEGATIVE
            parts.extend(
                [
                    f'<rect x="{x + 1}" y="{y + 1}" width="{layout.cell - 2}" '
                    f'height="22" rx="2" fill="{fill}" fill-opacity="{intensity:.3f}" '
                    f'data-motif-position="{support.motif_position}" '
                    f'data-candidate-position="{support.candidate_position}" '
                    f'data-llr-contribution="{support.llr_contribution:.17g}"/>',
                    text(
                        x + layout.cell / 2,
                        y + 16,
                        support.observed_base,
                        size=12,
                        anchor="middle",
                        weight=650,
                        fill=INK,
                        family="ui-monospace,monospace",
                    ),
                    text(
                        x + layout.cell / 2,
                        y + 35,
                        support_label(support.llr_contribution),
                        size=12,
                        anchor="middle",
                        fill=MUTED,
                        family="ui-monospace,monospace",
                        extra=(
                            ' class="llr-contribution-label" '
                            f'data-motif-position="{support.motif_position}" '
                            f'data-candidate-position="{support.candidate_position}"'
                        ),
                    ),
                ]
            )
        parts.append("</g>")
    parts.append("</g>")
    return parts
