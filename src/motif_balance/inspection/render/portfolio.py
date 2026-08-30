from __future__ import annotations

from motif_balance.errors import ArtifactError

from ..limits import MAX_SVG_CANDIDATES, MAX_SVG_MOTIFS
from ..model import ResultInspection
from .svg_primitives import (
    ACCENT,
    INK,
    LINE,
    MUTED,
    PAPER,
    POSITIVE,
    candidate_id,
    finish_svg,
    motif_id,
    svg_start,
    text,
)


def render_portfolio_svg(inspection: ResultInspection) -> bytes:
    """Render a deterministic candidate by motif score matrix."""

    candidates = inspection.portfolio.candidates[:MAX_SVG_CANDIDATES]
    if not candidates or not inspection.problem.motifs:
        raise ArtifactError("portfolio balance view requires candidates and motifs")
    for candidate in candidates:
        candidate_id(candidate.candidate_id)
    limiting_ids = {
        motif_id for candidate in candidates for motif_id in candidate.limiting_motif_ids
    }
    canonical_motifs = inspection.problem.motifs
    limiting_in_order = tuple(
        motif.motif_id for motif in canonical_motifs if motif.motif_id in limiting_ids
    )
    selected_ids = set(limiting_in_order[:MAX_SVG_MOTIFS])
    for motif in canonical_motifs:
        if len(selected_ids) >= MAX_SVG_MOTIFS:
            break
        selected_ids.add(motif.motif_id)
    motifs = tuple(motif for motif in canonical_motifs if motif.motif_id in selected_ids)
    displayed_limiting = sum(motif.motif_id in limiting_ids for motif in motifs)
    best_observed_rank = (
        "none"
        if inspection.portfolio.best_observed is None
        or inspection.portfolio.best_observed.selected_rank is None
        else str(inspection.portfolio.best_observed.selected_rank)
    )
    motif_ids = tuple(motif_id(motif.motif_id) for motif in motifs)
    observed_max = max(
        match.normalized_score
        for candidate in candidates
        for match in candidate.matches
        if match.motif_id in motif_ids
    )
    display_max = max(1.0, observed_max)
    is_legacy = inspection.problem.scoring_semantics == "normalized_llr_v1"
    score_description = (
        "normalized LLR from the clipped null-mean reference to the score maximum"
        if is_legacy
        else "relative PWM attainment from the attainable raw-LLR minimum to maximum"
    )
    reference_label = (
        "1.0 null-mean-to-score-maximum reference"
        if is_legacy
        else "1.0 score-maximizing PWM reference"
    )
    constraint_status = (
        "feasible"
        if all(candidate.constraint_status == "feasible" for candidate in candidates)
        else "mixed"
    )
    row_height = 34
    cell_width = 104
    left = 210
    extra_width = 310
    top = 140
    width = max(960, left + cell_width * len(motifs) + extra_width)
    height = top + row_height * len(candidates) + 92
    parts = svg_start(
        width=width,
        height=height,
        title_id="portfolio-balance-title",
        desc_id="portfolio-balance-desc",
        view_id="portfolio-balance-view",
    )
    parts.extend(
        [
            '<title id="portfolio-balance-title">Portfolio balance matrix</title>',
            '<desc id="portfolio-balance-desc">Candidate rows in deterministic rank order '
            "and motif columns in canonical design order. Each cell reports the exact "
            f"{score_description}; the score is not a probability.</desc>",
            f'<rect width="{width}" height="{height}" fill="{PAPER}"/>',
            text(20, 30, "Portfolio balance", size=18, weight=650),
            text(
                20,
                54,
                f"display scale 0 to {display_max:.6g} · {reference_label}",
                size=13,
                fill=MUTED,
            ),
            text(
                20,
                76,
                (
                    f"best observed {inspection.portfolio.best_observed_score:.6g} · "
                    + (
                        "sequence unavailable in source schema"
                        if inspection.portfolio.best_observed is None
                        else "not selected under the portfolio constraint"
                        if inspection.portfolio.best_observed.selected_rank is None
                        else f"selected at rank {inspection.portfolio.best_observed.selected_rank}"
                    )
                ),
                size=12,
                fill=MUTED,
            ),
            f'<g id="score-matrix" data-score-lower="0" data-score-upper="{display_max:.17g}" '
            f'data-best-observed-score="{inspection.portfolio.best_observed_score:.17g}" '
            f'data-best-observed-selected-rank="{best_observed_rank}" '
            f'data-constraint-status="{constraint_status}" '
            f'data-displayed-candidates="{len(candidates)}" '
            f'data-total-candidates="{len(inspection.portfolio.candidates)}" '
            f'data-displayed-motifs="{len(motifs)}" '
            f'data-total-motifs="{len(inspection.problem.motifs)}" '
            f'data-displayed-limiting="{displayed_limiting}" '
            f'data-total-limiting="{len(limiting_ids)}">',
        ]
    )
    for column, name in enumerate(motif_ids):
        parts.append(
            text(
                left + column * cell_width + cell_width / 2,
                116,
                name,
                size=12,
                anchor="middle",
                weight=650,
            )
        )
    parts.extend(
        [
            text(left + len(motifs) * cell_width + 16, 116, "balance_score", size=12, weight=650),
            text(left + len(motifs) * cell_width + 120, 116, "limiting motif", size=12, weight=650),
            text(left + len(motifs) * cell_width + 245, 116, "nearest", size=12, weight=650),
        ]
    )
    for row, candidate in enumerate(candidates):
        y = top + row * row_height
        parts.append(
            text(
                20,
                y + 21,
                f"rank {candidate.rank} · {candidate.candidate_id[-8:]}",
                size=12,
                family="ui-monospace,monospace",
            )
        )
        by_motif = {match.motif_id: match for match in candidate.matches}
        for column, name in enumerate(motif_ids):
            match = by_motif[name]
            x = left + column * cell_width
            intensity = 0.08 + 0.72 * min(1.0, match.normalized_score / display_max)
            stroke = ACCENT if name in candidate.limiting_motif_ids else LINE
            parts.extend(
                [
                    f'<rect x="{x}" y="{y}" width="{cell_width - 4}" height="{row_height - 4}" '
                    f'fill="{POSITIVE}" fill-opacity="{intensity:.3f}" stroke="{stroke}" '
                    f'data-candidate-rank="{candidate.rank}" data-motif-id="{name}" '
                    f'data-normalized-score="{match.normalized_score:.17g}"/>',
                    text(
                        x + (cell_width - 4) / 2,
                        y + 20,
                        f"{match.normalized_score:.6g}",
                        size=12,
                        anchor="middle",
                        weight=650,
                        family="ui-monospace,monospace",
                    ),
                ]
            )
        end = left + len(motifs) * cell_width
        parts.extend(
            [
                text(
                    end + 16,
                    y + 20,
                    f"{candidate.balance_score:.6g}",
                    size=12,
                    family="ui-monospace,monospace",
                ),
                text(end + 120, y + 20, ", ".join(candidate.limiting_motif_ids), size=12),
                text(
                    end + 245,
                    y + 20,
                    "—"
                    if candidate.nearest_neighbor_distance is None
                    else f"{candidate.nearest_neighbor_distance:.4g}",
                    size=12,
                    family="ui-monospace,monospace",
                ),
            ]
        )
    parts.append("</g>")
    reference_x = 20 + 180 * min(1.0, 1.0 / display_max)
    legend_y = height - 48
    parts.extend(
        [
            '<g id="score-legend">',
            f'<rect x="20" y="{legend_y}" width="180" height="10" '
            f'fill="{POSITIVE}" fill-opacity=".72"/>',
            f'<line x1="{reference_x:.3f}" y1="{legend_y - 4}" '
            f'x2="{reference_x:.3f}" y2="{legend_y + 14}" stroke="{INK}"/>',
            text(20, legend_y + 30, "0", size=12, fill=MUTED),
            text(200, legend_y + 30, f"{display_max:.6g}", size=12, anchor="end", fill=MUTED),
            text(
                reference_x,
                legend_y - 8,
                reference_label,
                size=12,
                anchor="middle",
            ),
            "</g>",
        ]
    )
    if len(candidates) < len(inspection.portfolio.candidates) or len(motifs) < len(
        inspection.problem.motifs
    ):
        parts.append(
            text(
                330,
                height - 18,
                f"Bounded view: {len(candidates)}/{len(inspection.portfolio.candidates)} "
                f"candidates and {len(motifs)}/{len(inspection.problem.motifs)} motifs.",
                size=12,
                fill=MUTED,
            )
        )
    if displayed_limiting < len(limiting_ids):
        parts.append(
            text(
                330,
                height - 4,
                f"Limiting motifs shown: {displayed_limiting}/{len(limiting_ids)}.",
                size=12,
                fill=MUTED,
            )
        )
    parts.append("</svg>")
    return finish_svg(parts)
