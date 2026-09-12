from __future__ import annotations

from typing import Literal

from ..model import InspectionCandidate, InspectionMatch, InspectionProblem
from .candidate_layout import (
    DNA_FONT_FAMILY,
    DNA_FONT_SIZE,
    VISUAL_CONTRACT,
    CandidateLayout,
    build_candidate_layout,
)
from .candidate_projection import shown_matches, validate_candidate_projection
from .information_logo import render_coordinate_aligned_information_logo
from .svg_primitives import INK, MUTED, finish_svg, motif_color, motif_id, safe_text, text


def _match_lane(match: InspectionMatch, *, top: int, layout: CandidateLayout) -> str:
    """Show projected strand bases, never derive a new match or reverse twice."""

    x = layout.left + match.start * layout.cell
    width = (match.end - match.start) * layout.cell
    color = motif_color(match.motif_id)
    bases = "".join(
        text(
            layout.left + (support.candidate_position + 0.5) * layout.cell,
            top + 15,
            support.observed_base,
            size=DNA_FONT_SIZE,
            fill="#FFFFFF",
            anchor="middle",
            weight=650,
            family=DNA_FONT_FAMILY,
            extra=(
                f' class="match-window-base" data-candidate-position="{support.candidate_position}"'
            ),
        )
        for support in sorted(match.position_support, key=lambda row: row.candidate_position)
    )
    left_prime, right_prime = (
        ("5\u2032", "3\u2032") if match.strand == "+" else ("3\u2032", "5\u2032")
    )
    return (
        f'<g class="motif-match" data-motif-id="{motif_id(match.motif_id)}" '
        f'data-motif-color="{color}" data-start="{match.start}" '
        f'data-end="{match.end}" data-strand="{match.strand}">'
        f'<rect x="{x}" y="{top}" width="{width}" height="20" '
        f'fill="{color}" stroke="{color}"/>{bases}'
        + text(x - 6, top + 15, left_prime, anchor="end", fill=MUTED)
        + text(x + width + 6, top + 15, right_prime, fill=MUTED)
        + "</g>"
    )


def _molecular_lanes(
    problem: InspectionProblem,
    candidate: InspectionCandidate,
    layout: CandidateLayout,
) -> list[str]:
    motifs = {motif.motif_id: motif for motif in (*problem.motifs, *problem.avoiders)}
    ceilings = {motif.motif_id: motif.score_ceiling for motif in problem.avoiders}
    parts = [
        f'<g id="motif-models" data-total-matches="{len(layout.shown)}" '
        f'data-displayed-matches="{len(layout.shown)}">'
    ]
    for matches, origin in (
        (layout.forward, layout.logo_top),
        (layout.reverse, layout.reverse_logo_top),
    ):
        for index, match in enumerate(matches):
            top = origin + index * layout.logo_row_height
            parts.append(
                render_coordinate_aligned_information_logo(
                    motifs[match.motif_id],
                    match,
                    top=top,
                    left=layout.left,
                    cell=layout.cell,
                    limiting=match.motif_id in candidate.limiting_motif_ids,
                    avoider=match.motif_id in ceilings,
                    score_ceiling=ceilings.get(match.motif_id),
                )
            )
            parts.append(
                _match_lane(
                    match,
                    top=top + 102 if match.strand == "+" else top - 24,
                    layout=layout,
                )
            )
    return [*parts, "</g>"]


def _duplex(candidate: InspectionCandidate, layout: CandidateLayout) -> list[str]:
    parts = ['<g id="duplex">']
    for group, sequence, baseline, primes in (
        ("primary-sequence", candidate.sequence, layout.primary_y, ("5\u2032", "3\u2032")),
        (
            "complementary-sequence",
            candidate.complement_sequence,
            layout.complement_y,
            ("3\u2032", "5\u2032"),
        ),
    ):
        parts.extend(
            [
                f'<g id="{group}">',
                text(layout.left - 12, baseline + 5, primes[0], anchor="end"),
            ]
        )
        for position, base in enumerate(sequence):
            parts.append(
                text(
                    layout.left + (position + 0.5) * layout.cell,
                    baseline + 5,
                    base,
                    size=DNA_FONT_SIZE,
                    anchor="middle",
                    weight=650,
                    family=DNA_FONT_FAMILY,
                    extra=f' data-candidate-position="{position}"',
                )
            )
        parts.extend(
            [
                text(layout.left + len(sequence) * layout.cell + 12, baseline + 5, primes[1]),
                "</g>",
            ]
        )
    for position in range(len(candidate.sequence)):
        x = layout.left + (position + 0.5) * layout.cell
        parts.append(
            f'<line x1="{x}" x2="{x}" y1="{layout.primary_y + 10}" '
            f'y2="{layout.complement_y - 12}" stroke="#D1D5DB"/>'
        )
    return [*parts, "</g>"]


def render_candidate_projection_svg(
    problem: InspectionProblem,
    candidate: InspectionCandidate,
    *,
    rank_scope: Literal["selected_portfolio", "caller_supplied_order"] = "selected_portfolio",
) -> bytes:
    """Render the current molecular visual contract from a bound projection."""

    validate_candidate_projection(problem, candidate)
    layout = build_candidate_layout(candidate, shown_matches(candidate))
    supplied = rank_scope == "caller_supplied_order"
    rank_description = (
        f"Caller-supplied rank {candidate.rank}; score replay only; "
        if supplied
        else f"Candidate rank {candidate.rank}; "
    )
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" id="candidate-realization-view" '
        f'data-visual-contract="{VISUAL_CONTRACT}" width="{layout.width}" '
        f'height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}" '
        'role="img" aria-labelledby="candidate-title candidate-desc">',
        '<title id="candidate-title">One DNA sequence, multiple motif preferences</title>',
        '<desc id="candidate-desc">',
        safe_text(
            rank_description + f"length {problem.length} nucleotides; "
            f"weakest requirement {candidate.balance_score:.6g}. "
            "Primary DNA runs 5\u2032\u21923\u2032; its coordinate-aligned complement "
            "runs 3\u2032\u21925\u2032. Selected windows "
            "contain white bases; model information logos color the observed base and leave "
            "other bases gray. Information in bits is distinct from motif matching scores. "
            "These are model-defined matches, not measured binding."
        ),
        "</desc>",
        f'<rect width="{layout.width}" height="{layout.height}" fill="#FFFFFF"/>',
        text(20, 28, "One DNA sequence, multiple motif preferences", size=18, weight=650),
        text(
            20,
            54,
            f"L = {problem.length} nt · weakest requirement = {candidate.balance_score:.4g}",
            size=14,
            fill=INK,
        ),
    ]
    parts.extend(_molecular_lanes(problem, candidate, layout))
    parts.extend(_duplex(candidate, layout))
    parts.append(
        text(
            20,
            layout.height - 14,
            (
                f"Caller-supplied rank {candidate.rank}; score replay, not source verification."
                if supplied
                else (
                    "Model preferences, not measured binding. "
                    "Exact scores and positions: inspection JSON."
                )
            ),
            fill=MUTED,
        )
    )
    parts.append("</svg>\n")
    return finish_svg(parts)
