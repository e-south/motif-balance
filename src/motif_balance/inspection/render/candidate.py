from __future__ import annotations

import math

from motif_balance.errors import ArtifactError

from ..limits import MAX_SVG_MATCHES
from ..model import InspectionCandidate, InspectionMatch, InspectionProblem, ResultInspection
from .information_logo import render_coordinate_aligned_information_logo
from .svg_primitives import (
    INK,
    MUTED,
    NEGATIVE,
    PAPER,
    POSITIVE,
    SHARED,
    candidate_id,
    finish_svg,
    motif_color,
    motif_id,
    safe_text,
    svg_start,
    text,
)

_MONOSPACE_CHARACTER_WIDTH = 8
_CELL_HORIZONTAL_PADDING = 12
_BASE_INDEX = {base: index for index, base in enumerate("ACGT")}


def _support_label(value: float) -> str:
    return f"{value:+.2g}"


def _candidate_cell_width(
    shown: tuple[InspectionMatch, ...],
) -> int:
    """Keep exact support labels readable, even for realistic long motifs."""

    labels = tuple(
        _support_label(support.llr_contribution)
        for match in shown
        for support in match.position_support
    )
    longest_label = max((len(label) for label in labels), default=0)
    label_width = longest_label * _MONOSPACE_CHARACTER_WIDTH + _CELL_HORIZONTAL_PADDING
    return max(44, label_width)


def _candidate(inspection: ResultInspection, rank: int) -> InspectionCandidate:
    for candidate in inspection.portfolio.candidates:
        if candidate.rank == rank:
            candidate_id(candidate.candidate_id)
            return candidate
    raise ArtifactError(f"candidate rank {rank} is not present in this result")


def _shown_matches(candidate: InspectionCandidate) -> tuple[InspectionMatch, ...]:
    ordered = tuple(
        sorted(
            (*candidate.matches, *candidate.avoidance_matches),
            key=lambda match: (
                match.motif_id not in candidate.limiting_motif_ids,
                match.motif_id,
                match.start,
                match.strand,
            ),
        )
    )
    return ordered[:MAX_SVG_MATCHES]


def _validate_candidate_projection(
    problem: InspectionProblem,
    candidate: InspectionCandidate,
) -> None:
    target_ids = {motif.motif_id for motif in problem.motifs}
    avoider_ids = {motif.motif_id for motif in problem.avoiders}
    if (
        len(candidate.sequence) != problem.length
        or {match.motif_id for match in candidate.matches} != target_ids
        or {match.motif_id for match in candidate.avoidance_matches} != avoider_ids
    ):
        raise ArtifactError("candidate render projection does not match its problem")
    motifs_by_id = {motif.motif_id: motif for motif in (*problem.motifs, *problem.avoiders)}
    for match in (*candidate.matches, *candidate.avoidance_matches):
        motif = motifs_by_id[match.motif_id]
        if match.end - match.start != motif.width:
            raise ArtifactError("candidate render projection does not match its problem")
        for support in match.position_support:
            base_index = _BASE_INDEX[support.observed_base]
            expected_base = (
                candidate.sequence[support.candidate_position]
                if match.strand == "+"
                else candidate.complement_sequence[support.candidate_position]
            )
            expected_probability = motif.probabilities[support.motif_position][base_index]
            expected_background = motif.background[base_index]
            if (
                support.observed_base != expected_base
                or not math.isclose(
                    support.model_probability,
                    expected_probability,
                    rel_tol=0.0,
                    abs_tol=1.0e-12,
                )
                or not math.isclose(
                    support.background_probability,
                    expected_background,
                    rel_tol=0.0,
                    abs_tol=1.0e-12,
                )
            ):
                raise ArtifactError("candidate render projection does not match its problem")


def _match_lane(
    match: InspectionMatch,
    *,
    lane: int,
    primary_y: int,
    complement_y: int,
    left: int,
    cell: int,
    limiting: bool,
    avoider: bool,
    score_ceiling: float | None,
) -> str:
    x = left + match.start * cell
    width = (match.end - match.start) * cell
    if match.strand == "+":
        y = primary_y - 22 - lane * 30
        label_y = y - 4
    else:
        y = complement_y + 10 + lane * 30
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
        f"{dash_attribute}/>"
        f"{match_label}"
        "</g>"
    )


def render_candidate_svg(
    inspection: ResultInspection,
    *,
    candidate_rank: int = 1,
) -> bytes:
    """Render the exact strand-aware realization for one selected candidate."""

    candidate = _candidate(inspection, candidate_rank)
    return _render_candidate_projection_svg(inspection.problem, candidate)


def _render_candidate_projection_svg(
    problem: InspectionProblem,
    candidate: InspectionCandidate,
) -> bytes:
    """Render a candidate selected from the same verified result inspection."""

    _validate_candidate_projection(problem, candidate)
    shown = _shown_matches(candidate)
    motifs_by_id = {motif.motif_id: motif for motif in (*problem.motifs, *problem.avoiders)}
    avoider_ceilings = {motif.motif_id: motif.score_ceiling for motif in problem.avoiders}
    forward = tuple(match for match in shown if match.strand == "+")
    reverse = tuple(match for match in shown if match.strand == "-")
    cell = _candidate_cell_width(shown)
    left = 210
    right = 42
    width = max(960, left + len(candidate.sequence) * cell + right)
    logo_top = 88
    logo_row_height = 128
    primary_y = logo_top + logo_row_height * len(forward) + 42 + 30 * max(1, len(forward))
    complement_y = primary_y + 44
    reverse_logo_top = complement_y + 44 + 30 * max(1, len(reverse))
    support_y = reverse_logo_top + logo_row_height * len(reverse) + 32
    height = support_y + 40 * len(shown) + 72
    parts = svg_start(
        width=width,
        height=height,
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
            f'<rect width="{width}" height="{height}" fill="{PAPER}"/>',
            text(20, 30, "Candidate realization", size=18, weight=650),
            text(
                20,
                54,
                f"rank {candidate.rank} · balance {candidate.balance_score:.6g} · "
                f"limiting {limiting}",
                size=13,
                fill=MUTED,
            ),
            f'<g id="motif-models" data-displayed-matches="{len(shown)}" '
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
                    top=logo_top + index * logo_row_height,
                    left=left,
                    cell=cell,
                    limiting=match.motif_id in candidate.limiting_motif_ids,
                    avoider=match.motif_id in avoider_ceilings,
                    score_ceiling=avoider_ceilings.get(match.motif_id),
                )
                for index, match in enumerate(forward)
            ),
            *(
                render_coordinate_aligned_information_logo(
                    motifs_by_id[match.motif_id],
                    match,
                    top=reverse_logo_top + index * logo_row_height,
                    left=left,
                    cell=cell,
                    limiting=match.motif_id in candidate.limiting_motif_ids,
                    avoider=match.motif_id in avoider_ceilings,
                    score_ceiling=avoider_ceilings.get(match.motif_id),
                )
                for index, match in enumerate(reverse)
            ),
            "</g>",
            '<g id="shared-coordinates">',
        ]
    )
    for position in candidate.shared_coordinates:
        x = left + position * cell
        parts.append(
            f'<rect x="{x}" y="{primary_y - 18}" width="{cell}" height="58" '
            f'fill="{SHARED}" fill-opacity=".55" data-candidate-position="{position}"/>'
        )
    parts.extend(
        [
            "</g>",
            '<g id="forward-matches">',
            *(
                _match_lane(
                    match,
                    lane=index,
                    primary_y=primary_y,
                    complement_y=complement_y,
                    left=left,
                    cell=cell,
                    limiting=match.motif_id in candidate.limiting_motif_ids,
                    avoider=match.motif_id in avoider_ceilings,
                    score_ceiling=avoider_ceilings.get(match.motif_id),
                )
                for index, match in enumerate(forward)
            ),
            "</g>",
            '<g id="primary-sequence">',
            text(20, primary_y + 5, "Primary 5\u2032\u21923\u2032", size=12, weight=650),
            text(left - 12, primary_y + 5, "5\u2032", size=12, anchor="end", fill=MUTED),
        ]
    )
    for position, base in enumerate(candidate.sequence):
        base_x = left + (position + 0.5) * cell
        parts.extend(
            [
                text(
                    base_x,
                    primary_y + 5,
                    base,
                    size=14,
                    anchor="middle",
                    weight=650,
                    family="ui-monospace,monospace",
                    extra=f' data-candidate-position="{position}"',
                ),
                text(base_x, primary_y + 23, position, size=12, anchor="middle", fill=MUTED),
            ]
        )
    parts.extend(
        [
            text(
                left + len(candidate.sequence) * cell + 12,
                primary_y + 5,
                "3\u2032",
                size=12,
            ),
            "</g>",
            '<g id="complementary-sequence">',
            text(
                20,
                complement_y + 5,
                "Complement 3\u2032\u21925\u2032",
                size=12,
                weight=650,
            ),
            text(left - 12, complement_y + 5, "3\u2032", size=12, anchor="end", fill=MUTED),
        ]
    )
    for position, base in enumerate(candidate.complement_sequence):
        base_x = left + (position + 0.5) * cell
        parts.append(
            text(
                base_x,
                complement_y + 5,
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
                left + len(candidate.sequence) * cell + 12,
                complement_y + 5,
                "5\u2032",
                size=12,
            ),
            "</g>",
            '<g id="reverse-matches">',
            *(
                _match_lane(
                    match,
                    lane=index,
                    primary_y=primary_y,
                    complement_y=complement_y,
                    left=left,
                    cell=cell,
                    limiting=match.motif_id in candidate.limiting_motif_ids,
                    avoider=match.motif_id in avoider_ceilings,
                    score_ceiling=avoider_ceilings.get(match.motif_id),
                )
                for index, match in enumerate(reverse)
            ),
            "</g>",
            f'<g id="position-support" data-cell-width="{cell}">',
            text(
                20,
                support_y - 12,
                "Observed-base positional support (raw LLR contributions)",
                size=12,
                weight=650,
            ),
        ]
    )
    for row, match in enumerate(shown):
        y = support_y + row * 40
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
            f'<line x1="{left}" y1="{y + 12}" x2="{left + len(candidate.sequence) * cell}" '
            f'y2="{y + 12}" stroke="{color}" stroke-width="1.5"/>'
        )
        for support in match.position_support:
            x = left + support.candidate_position * cell
            intensity = min(0.85, 0.18 + abs(support.llr_contribution) / 5)
            fill = POSITIVE if support.llr_contribution >= 0 else NEGATIVE
            parts.extend(
                [
                    f'<rect x="{x + 1}" y="{y + 1}" width="{cell - 2}" height="22" rx="2" '
                    f'fill="{fill}" fill-opacity="{intensity:.3f}" '
                    f'data-motif-position="{support.motif_position}" '
                    f'data-candidate-position="{support.candidate_position}" '
                    f'data-llr-contribution="{support.llr_contribution:.17g}"/>',
                    text(
                        x + cell / 2,
                        y + 16,
                        support.observed_base,
                        size=12,
                        anchor="middle",
                        weight=650,
                        fill=INK,
                        family="ui-monospace,monospace",
                    ),
                    text(
                        x + cell / 2,
                        y + 35,
                        _support_label(support.llr_contribution),
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
    total_matches = len(candidate.matches) + len(candidate.avoidance_matches)
    if len(shown) < total_matches:
        parts.append(
            text(
                20,
                height - 18,
                f"Showing {len(shown)} of {total_matches} matches; "
                "exact records remain in the inspection JSON.",
                size=12,
                fill=MUTED,
            )
        )
    elif candidate.shared_coordinates:
        parts.append(
            text(
                20,
                height - 18,
                f"Shared-coordinate union: {len(candidate.shared_coordinates)} positions. "
                "Overlap is not evidence of simultaneous occupancy.",
                size=12,
                fill=MUTED,
            )
        )
    parts.append("</svg>\n")
    return finish_svg(parts)
