from __future__ import annotations

from motif_balance.errors import ArtifactError

from ..limits import MAX_SVG_MATCHES
from ..model import InspectionCandidate, InspectionMatch, InspectionMotif, ResultInspection
from .svg_primitives import (
    ACCENT,
    INK,
    LINE,
    MUTED,
    NEGATIVE,
    PAPER,
    POSITIVE,
    SHARED,
    candidate_id,
    finish_svg,
    motif_id,
    safe_text,
    svg_start,
    text,
)

_BASE_COLORS = {"A": "#1B7F5A", "C": "#315F9E", "G": "#B7791F", "T": "#B64A3A"}
_MONOSPACE_CHARACTER_WIDTH = 8
_CELL_HORIZONTAL_PADDING = 12


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
    color = NEGATIVE if avoider else ACCENT if limiting else POSITIVE
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
    return (
        f'<g class="motif-match" data-motif-id="{motif_id(match.motif_id)}" '
        f"{role_attribute}"
        f"{ceiling_attribute}"
        f'data-start="{match.start}" data-end="{match.end}" data-strand="{match.strand}">'
        f'<rect x="{x}" y="{y}" width="{width}" height="16" rx="3" '
        f'fill="{color}" fill-opacity=".18" stroke="{color}" stroke-width="1.5"/>'
        f"{text(x, label_y, label, size=12, fill=INK, family='ui-monospace,monospace')}"
        "</g>"
    )


def _motif_model(
    motif: InspectionMotif,
    match: InspectionMatch,
    *,
    top: int,
    left: int,
    cell: int,
) -> str:
    """Render one fixed-glyph probability strip beside its selected match contract."""

    model_name = motif_id(motif.motif_id)
    score_label = (
        "normalized score"
        if motif.score_reference_semantics == "null_mean_to_score_max_v1"
        else "attainment"
    )
    matrix_top = top + 46
    parts = [
        f'<g class="motif-model" data-motif-id="{model_name}" '
        'data-display-convention="fixed-glyph-probability-strip" '
        f'data-model-digest="{motif.model_digest}" data-match-start="{match.start}" '
        f'data-match-end="{match.end}" data-match-strand="{match.strand}" '
        f'data-probability-consensus="{motif.probability_consensus}" '
        f'data-score-maximizing-sequence="{motif.score_maximizing_sequence}" '
        f'data-score-min="{motif.score_min:.17g}" data-score-max="{motif.score_max:.17g}">',
        text(20, top + 18, model_name, size=12, weight=650),
        text(
            20,
            top + 38,
            f"width {motif.width} · {score_label} {match.normalized_score:.4g} · "
            f"best [{match.start}, {match.end}) {match.strand}",
            size=12,
            fill=MUTED,
        ),
    ]
    for position, row in enumerate(motif.probabilities):
        x = left + position * cell
        for base_index, (base, probability) in enumerate(zip("ACGT", row, strict=True)):
            y = matrix_top + base_index * 14
            parts.extend(
                [
                    f'<rect x="{x + 1}" y="{y - 10}" '
                    f'width="{(cell - 2) * probability:.3f}" height="12" rx="2" '
                    f'fill="{_BASE_COLORS[base]}" fill-opacity=".28" '
                    f'data-motif-position="{position}" data-base="{base}" '
                    f'data-probability="{probability:.17g}"/>',
                    text(
                        x + cell / 2,
                        y,
                        base,
                        size=12,
                        anchor="middle",
                        weight=700,
                        fill=INK,
                        family="ui-monospace,monospace",
                        extra=(
                            f' data-motif-position="{position}" data-base="{base}" '
                            f'data-probability="{probability:.17g}"'
                        ),
                    ),
                ]
            )
        parts.append(
            text(
                left + (position + 0.5) * cell,
                matrix_top + 59,
                position,
                size=12,
                anchor="middle",
                fill=MUTED,
            )
        )
    parts.append("</g>")
    return "".join(parts)


def render_candidate_svg(
    inspection: ResultInspection,
    *,
    candidate_rank: int = 1,
) -> bytes:
    """Render the exact strand-aware realization for one selected candidate."""

    candidate = _candidate(inspection, candidate_rank)
    shown = _shown_matches(candidate)
    motifs_by_id = {
        motif.motif_id: motif
        for motif in (*inspection.problem.motifs, *inspection.problem.avoiders)
    }
    avoider_ceilings = {
        motif.motif_id: motif.score_ceiling for motif in inspection.problem.avoiders
    }
    forward = tuple(match for match in shown if match.strand == "+")
    reverse = tuple(match for match in shown if match.strand == "-")
    cell = _candidate_cell_width(shown)
    left = 210
    right = 42
    width = max(960, left + len(candidate.sequence) * cell + right)
    logo_top = 88
    logo_row_height = 128
    primary_y = logo_top + logo_row_height * len(shown) + 42 + 30 * max(1, len(forward))
    complement_y = primary_y + 44
    support_y = complement_y + 44 + 30 * max(1, len(reverse))
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
                f"rank {candidate.rank} · balance_score {candidate.balance_score:.6g} · "
                f"limiting {limiting}",
                size=13,
                fill=MUTED,
            ),
            f'<g id="motif-models" data-displayed-matches="{len(shown)}" '
            f'data-total-matches="{len(candidate.matches) + len(candidate.avoidance_matches)}">',
            text(
                20,
                78,
                "Supplied motif models (fixed-glyph probability strips) → selected matches",
                size=12,
                weight=650,
            ),
            *(
                _motif_model(
                    motifs_by_id[match.motif_id],
                    match,
                    top=logo_top + index * logo_row_height,
                    left=left,
                    cell=cell,
                )
                for index, match in enumerate(shown)
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
            f'y2="{y + 12}" stroke="{LINE}"/>'
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
    parts.append("</svg>")
    return finish_svg(parts)
