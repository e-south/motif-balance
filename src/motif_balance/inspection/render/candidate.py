from __future__ import annotations

import math

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


def _candidate(inspection: ResultInspection, rank: int) -> InspectionCandidate:
    for candidate in inspection.portfolio.candidates:
        if candidate.rank == rank:
            candidate_id(candidate.candidate_id)
            return candidate
    raise ArtifactError(f"candidate rank {rank} is not present in this result")


def _shown_matches(candidate: InspectionCandidate) -> tuple[InspectionMatch, ...]:
    ordered = tuple(
        sorted(
            candidate.matches,
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
) -> str:
    x = left + match.start * cell
    width = (match.end - match.start) * cell
    if match.strand == "+":
        y = primary_y - 22 - lane * 30
        label_y = y - 4
    else:
        y = complement_y + 10 + lane * 30
        label_y = y + 30
    color = ACCENT if limiting else POSITIVE
    label = (
        f"{motif_id(match.motif_id)} · {match.normalized_score:.6g} · "
        f"{match.strand} · [{match.start}, {match.end})"
    )
    return (
        f'<g class="motif-match" data-motif-id="{motif_id(match.motif_id)}" '
        f'data-start="{match.start}" data-end="{match.end}" data-strand="{match.strand}">'
        f'<rect x="{x}" y="{y}" width="{width}" height="16" rx="3" '
        f'fill="{color}" fill-opacity=".18" stroke="{color}" stroke-width="1.5"/>'
        f"{text(x, label_y, label, size=11, fill=INK, family='ui-monospace,monospace')}"
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
    """Render one small information-weighted logo beside its selected match contract."""

    model_name = motif_id(motif.motif_id)
    baseline = top + 58
    parts = [
        f'<g class="motif-model" data-motif-id="{model_name}" '
        f'data-model-digest="{motif.model_digest}" data-match-start="{match.start}" '
        f'data-match-end="{match.end}" data-match-strand="{match.strand}" '
        f'data-probability-consensus="{motif.probability_consensus}" '
        f'data-score-maximizing-sequence="{motif.score_maximizing_sequence}" '
        f'data-score-min="{motif.score_min:.17g}" data-score-max="{motif.score_max:.17g}">',
        text(20, top + 18, model_name, size=12, weight=650),
        text(
            20,
            top + 38,
            f"width {motif.width} · attainment {match.normalized_score:.4g} · "
            f"best [{match.start}, {match.end}) {match.strand}",
            size=10,
            fill=MUTED,
        ),
        f'<line x1="{left}" y1="{baseline}" x2="{left + motif.width * cell}" '
        f'y2="{baseline}" stroke="{LINE}"/>',
    ]
    for position, row in enumerate(motif.probabilities):
        information = max(0.0, 2.0 + math.fsum(p * math.log2(p) for p in row))
        glyphs = sorted(zip("ACGT", row, strict=True), key=lambda item: (item[1], item[0]))
        cursor = float(baseline)
        for base, probability in glyphs:
            glyph_height = max(4, round(54 * probability * information / 2.0))
            cursor -= glyph_height
            parts.append(
                text(
                    left + (position + 0.5) * cell,
                    cursor + glyph_height,
                    base,
                    size=glyph_height,
                    anchor="middle",
                    weight=700,
                    fill=_BASE_COLORS[base],
                    family="ui-monospace,monospace",
                    extra=(
                        f' data-motif-position="{position}" data-base="{base}" '
                        f'data-probability="{probability:.17g}"'
                    ),
                )
            )
        parts.append(
            text(
                left + (position + 0.5) * cell,
                baseline + 13,
                position,
                size=8,
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
    motifs_by_id = {motif.motif_id: motif for motif in inspection.problem.motifs}
    forward = tuple(match for match in shown if match.strand == "+")
    reverse = tuple(match for match in shown if match.strand == "-")
    cell = 24
    left = 210
    right = 42
    width = max(960, left + len(candidate.sequence) * cell + right)
    logo_top = 88
    logo_row_height = 82
    primary_y = logo_top + logo_row_height * len(shown) + 42 + 30 * max(1, len(forward))
    complement_y = primary_y + 44
    support_y = complement_y + 44 + 30 * max(1, len(reverse))
    height = support_y + 34 * len(shown) + 70
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
            '<g id="motif-models">',
            text(
                20,
                78,
                "Supplied motif models (information-weighted logos) → selected matches",
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
                )
                for index, match in enumerate(forward)
            ),
            "</g>",
            '<g id="primary-sequence">',
            text(20, primary_y + 5, "Primary 5\u2032\u21923\u2032", size=12, weight=650),
            text(left - 12, primary_y + 5, "5\u2032", size=11, anchor="end", fill=MUTED),
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
                text(base_x, primary_y + 20, position, size=8, anchor="middle", fill=MUTED),
            ]
        )
    parts.extend(
        [
            text(
                left + len(candidate.sequence) * cell + 12,
                primary_y + 5,
                "3\u2032",
                size=11,
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
            text(left - 12, complement_y + 5, "3\u2032", size=11, anchor="end", fill=MUTED),
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
                size=11,
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
                )
                for index, match in enumerate(reverse)
            ),
            "</g>",
            '<g id="position-support">',
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
        y = support_y + row * 34
        parts.append(
            text(
                20,
                y + 17,
                f"{match.motif_id} {match.strand} · raw {match.raw_score:.4g}",
                size=11,
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
                        size=10,
                        anchor="middle",
                        weight=650,
                        fill=INK,
                        family="ui-monospace,monospace",
                    ),
                    text(
                        x + cell / 2,
                        y + 31,
                        f"{support.llr_contribution:+.2g}",
                        size=8,
                        anchor="middle",
                        fill=MUTED,
                        family="ui-monospace,monospace",
                    ),
                ]
            )
    parts.append("</g>")
    if len(shown) < len(candidate.matches):
        parts.append(
            text(
                20,
                height - 18,
                f"Showing {len(shown)} of {len(candidate.matches)} matches; "
                "exact records remain in the inspection JSON.",
                size=11,
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
                size=11,
                fill=MUTED,
            )
        )
    parts.append("</svg>")
    return finish_svg(parts)
