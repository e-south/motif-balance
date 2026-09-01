from __future__ import annotations

from ..model import InspectionCandidate, InspectionMatch, InspectionProblem
from .candidate_layout import CandidateLayout, build_candidate_layout
from .candidate_projection import shown_matches, validate_candidate_projection
from .candidate_support import render_position_support
from .information_logo import render_coordinate_aligned_information_logo
from .svg_primitives import (
    INK,
    MUTED,
    PAPER,
    SHARED,
    finish_svg,
    motif_color,
    motif_id,
    safe_text,
    svg_start,
    text,
)


def _match_lane(
    match: InspectionMatch,
    *,
    lane: int,
    layout: CandidateLayout,
    limiting: bool,
    avoider: bool,
    score_ceiling: float | None,
) -> str:
    x = layout.left + match.start * layout.cell
    width = (match.end - match.start) * layout.cell
    if match.strand == "+":
        y = layout.primary_y - 22 - lane * 30
        label_y = y - 4
    else:
        y = layout.complement_y + 10 + lane * 30
        label_y = y + 30
    color = motif_color(match.motif_id)
    ceiling_label = (
        f" · ceiling {score_ceiling:.6g}" if avoider and score_ceiling is not None else ""
    )
    label = (
        f"{motif_id(match.motif_id)} · {match.normalized_score:.6g} · "
        f"{match.strand} · [{match.start}, {match.end}){ceiling_label}"
    )
    ceiling_attribute = (
        f'data-score-ceiling="{score_ceiling:.17g}" '
        if avoider and score_ceiling is not None
        else ""
    )
    role_attribute = 'data-role="avoider" ' if avoider else ""
    limiting_attribute = f'data-limiting="{str(limiting).lower()}" '
    dash_attribute = 'stroke-dasharray="6 4" ' if avoider else ""
    limiting_label = " · LIMITING" if limiting else ""
    match_label = text(
        x,
        label_y,
        label + limiting_label,
        size=12,
        fill=INK,
        family="ui-monospace,monospace",
    )
    return (
        f'<g class="motif-match" data-motif-id="{motif_id(match.motif_id)}" '
        f'data-motif-color="{color}" '
        f"{role_attribute}"
        f"{limiting_attribute}"
        f"{ceiling_attribute}"
        f'data-start="{match.start}" data-end="{match.end}" data-strand="{match.strand}">'
        f'<rect x="{x}" y="{y}" width="{width}" height="16" rx="3" '
        f'fill="{color}" fill-opacity=".18" stroke="{color}" '
        f'stroke-width="{3 if limiting else 1.5}" '
        f"{dash_attribute}/>{match_label}</g>"
    )


def _render_opening(candidate: InspectionCandidate, layout: CandidateLayout) -> list[str]:
    parts = svg_start(
        width=layout.width,
        height=layout.height,
        title_id="candidate-realization-title",
        desc_id="candidate-realization-desc",
        view_id="candidate-realization-view",
    )
    limiting = ", ".join(candidate.limiting_motif_ids)
    parts.extend(
        [
            '<title id="candidate-realization-title">Candidate realization</title>',
            '<desc id="candidate-realization-desc">',
            safe_text(
                f"Candidate rank {candidate.rank}. The primary strand is shown 5 prime to 3 prime "
                "and its coordinate-aligned complement 3 prime to 5 prime. Forward matches are "
                "above, reverse matches below, and signed observed-base log-likelihood "
                "contributions are shown by motif."
            ),
            "</desc>",
            f'<rect width="{layout.width}" height="{layout.height}" fill="{PAPER}"/>',
            text(20, 30, "Candidate realization", size=18, weight=650),
            text(
                20,
                54,
                f"rank {candidate.rank} · balance {candidate.balance_score:.6g} · "
                f"limiting {limiting}",
                size=13,
                fill=MUTED,
            ),
        ]
    )
    return parts


def _render_model_logos(
    problem: InspectionProblem,
    candidate: InspectionCandidate,
    layout: CandidateLayout,
) -> list[str]:
    motifs_by_id = {motif.motif_id: motif for motif in (*problem.motifs, *problem.avoiders)}
    avoider_ceilings = {motif.motif_id: motif.score_ceiling for motif in problem.avoiders}
    return [
        f'<g id="motif-models" data-displayed-matches="{len(layout.shown)}" '
        f'data-total-matches="{len(candidate.matches) + len(candidate.avoidance_matches)}">',
        text(
            20,
            78,
            "Supplied motif models (0 to 2 bit information logos) → selected matches",
            size=12,
            weight=650,
        ),
        *(
            render_coordinate_aligned_information_logo(
                motifs_by_id[match.motif_id],
                match,
                top=layout.logo_top + index * layout.logo_row_height,
                left=layout.left,
                cell=layout.cell,
                limiting=match.motif_id in candidate.limiting_motif_ids,
                avoider=match.motif_id in avoider_ceilings,
                score_ceiling=avoider_ceilings.get(match.motif_id),
            )
            for index, match in enumerate(layout.forward)
        ),
        *(
            render_coordinate_aligned_information_logo(
                motifs_by_id[match.motif_id],
                match,
                top=layout.reverse_logo_top + index * layout.logo_row_height,
                left=layout.left,
                cell=layout.cell,
                limiting=match.motif_id in candidate.limiting_motif_ids,
                avoider=match.motif_id in avoider_ceilings,
                score_ceiling=avoider_ceilings.get(match.motif_id),
            )
            for index, match in enumerate(layout.reverse)
        ),
        "</g>",
    ]


def _render_shared_coordinates(
    candidate: InspectionCandidate,
    layout: CandidateLayout,
) -> list[str]:
    parts = ['<g id="shared-coordinates">']
    for position in candidate.shared_coordinates:
        x = layout.left + position * layout.cell
        parts.append(
            f'<rect x="{x}" y="{layout.primary_y - 18}" width="{layout.cell}" height="58" '
            f'fill="{SHARED}" fill-opacity=".55" data-candidate-position="{position}"/>'
        )
    parts.append("</g>")
    return parts


def _render_duplex_and_matches(
    problem: InspectionProblem,
    candidate: InspectionCandidate,
    layout: CandidateLayout,
) -> list[str]:
    avoider_ceilings = {motif.motif_id: motif.score_ceiling for motif in problem.avoiders}
    parts = [
        '<g id="forward-matches">',
        *(
            _match_lane(
                match,
                lane=index,
                layout=layout,
                limiting=match.motif_id in candidate.limiting_motif_ids,
                avoider=match.motif_id in avoider_ceilings,
                score_ceiling=avoider_ceilings.get(match.motif_id),
            )
            for index, match in enumerate(layout.forward)
        ),
        "</g>",
        '<g id="primary-sequence">',
        text(20, layout.primary_y + 5, "Primary 5\u2032\u21923\u2032", size=12, weight=650),
        text(
            layout.left - 12,
            layout.primary_y + 5,
            "5\u2032",
            size=12,
            anchor="end",
            fill=MUTED,
        ),
    ]
    for position, base in enumerate(candidate.sequence):
        base_x = layout.left + (position + 0.5) * layout.cell
        parts.extend(
            [
                text(
                    base_x,
                    layout.primary_y + 5,
                    base,
                    size=14,
                    anchor="middle",
                    weight=650,
                    family="ui-monospace,monospace",
                    extra=f' data-candidate-position="{position}"',
                ),
                text(base_x, layout.primary_y + 23, position, size=12, anchor="middle", fill=MUTED),
            ]
        )
    parts.extend(
        [
            text(
                layout.left + len(candidate.sequence) * layout.cell + 12,
                layout.primary_y + 5,
                "3\u2032",
                size=12,
            ),
            "</g>",
            '<g id="complementary-sequence">',
            text(
                20,
                layout.complement_y + 5,
                "Complement 3\u2032\u21925\u2032",
                size=12,
                weight=650,
            ),
            text(
                layout.left - 12,
                layout.complement_y + 5,
                "3\u2032",
                size=12,
                anchor="end",
                fill=MUTED,
            ),
        ]
    )
    for position, base in enumerate(candidate.complement_sequence):
        base_x = layout.left + (position + 0.5) * layout.cell
        parts.append(
            text(
                base_x,
                layout.complement_y + 5,
                base,
                size=14,
                anchor="middle",
                weight=650,
                family="ui-monospace,monospace",
                extra=f' data-candidate-position="{position}"',
            )
        )
    parts.extend(
        [
            text(
                layout.left + len(candidate.sequence) * layout.cell + 12,
                layout.complement_y + 5,
                "5\u2032",
                size=12,
            ),
            "</g>",
            '<g id="reverse-matches">',
            *(
                _match_lane(
                    match,
                    lane=index,
                    layout=layout,
                    limiting=match.motif_id in candidate.limiting_motif_ids,
                    avoider=match.motif_id in avoider_ceilings,
                    score_ceiling=avoider_ceilings.get(match.motif_id),
                )
                for index, match in enumerate(layout.reverse)
            ),
            "</g>",
        ]
    )
    return parts


def _render_footer(candidate: InspectionCandidate, layout: CandidateLayout) -> list[str]:
    total_matches = len(candidate.matches) + len(candidate.avoidance_matches)
    parts: list[str] = []
    if len(layout.shown) < total_matches:
        parts.append(
            text(
                20,
                layout.height - 18,
                f"Showing {len(layout.shown)} of {total_matches} matches; "
                "exact records remain in the inspection JSON.",
                size=12,
                fill=MUTED,
            )
        )
    elif candidate.shared_coordinates:
        parts.append(
            text(
                20,
                layout.height - 18,
                f"Shared-coordinate union: {len(candidate.shared_coordinates)} positions. "
                "Overlap is not evidence of simultaneous occupancy.",
                size=12,
                fill=MUTED,
            )
        )
    parts.append("</svg>\n")
    return parts


def render_candidate_projection_svg(
    problem: InspectionProblem,
    candidate: InspectionCandidate,
) -> bytes:
    """Render a candidate selected from the same verified result inspection."""

    validate_candidate_projection(problem, candidate)
    layout = build_candidate_layout(candidate, shown_matches(candidate))
    parts = _render_opening(candidate, layout)
    parts.extend(_render_model_logos(problem, candidate, layout))
    parts.extend(_render_shared_coordinates(candidate, layout))
    parts.extend(_render_duplex_and_matches(problem, candidate, layout))
    parts.extend(render_position_support(candidate, layout))
    parts.extend(_render_footer(candidate, layout))
    return finish_svg(parts)
