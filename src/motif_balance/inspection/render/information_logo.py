from __future__ import annotations

import math

from motif_balance.errors import ArtifactError

from ..model import InspectionMatch, InspectionMotif
from .logo_shapes import PIXELS_PER_BIT, information_letter
from .logo_shapes import information_bits as column_information
from .svg_primitives import INK, MUTED, motif_color, motif_id, text

_ALPHABET = "ACGT"
_ALTERNATIVE = "#D1D5DB"


def _letter(
    *,
    base: str,
    probability: float,
    information_bits: float,
    observed_base: str,
    color: str,
    center_x: float,
    bottom_y: float,
    width: float,
    glyph_id: str,
) -> str:
    observed = base == observed_base
    return information_letter(
        base=base,
        probability=probability,
        bits=information_bits,
        color=color if observed else _ALTERNATIVE,
        observed=observed,
        center_x=center_x,
        bottom_y=bottom_y,
        width=width,
        glyph_id=glyph_id,
    )


def render_coordinate_aligned_information_logo(
    motif: InspectionMotif,
    match: InspectionMatch,
    *,
    top: int,
    left: int,
    cell: int,
    limiting: bool,
    avoider: bool,
    score_ceiling: float | None,
) -> str:
    """Render a model logo from an already projected representative match.

    Candidate coordinates and observed bases come exclusively from position_support;
    this renderer neither scans the sequence nor recomputes a motif score.
    """

    if avoider and score_ceiling is None:
        raise ArtifactError("avoider information logo requires a score ceiling")
    if any(
        not math.isclose(probability, 0.25, rel_tol=0.0, abs_tol=1.0e-12)
        for probability in motif.background
    ):
        raise ArtifactError(
            f"information logo requires uniform background; motif {motif.motif_id!r} "
            f"declares {motif.background}"
        )
    model_name = motif_id(motif.motif_id)
    color = motif_color(motif.motif_id)
    score_label = (
        "normalized score"
        if motif.score_reference_semantics == "null_mean_to_score_max_v1"
        else "attainment"
    )
    role = match.spec_direction or ("avoider" if avoider else "target")
    logo_bottom = top + 96
    match_left = left + match.start * cell
    match_width = (match.end - match.start) * cell
    parts = [
        f'<g class="motif-information-logo" data-motif-id="{model_name}" '
        'data-display-convention="coordinate-aligned-information-logo" '
        'data-information-scale="uniform-background-0-to-2-bits" '
        f'data-duplex-side="{"primary" if match.strand == "+" else "complement"}" '
        f'data-motif-color="{color}" '
        f'data-role="{role}" data-limiting="{str(limiting).lower()}" '
        + (
            f'data-direction="{match.spec_direction}" '
            f'data-spec-satisfaction="{match.spec_satisfaction:.17g}" '
            if match.spec_direction is not None and match.spec_satisfaction is not None
            else ""
        )
        + f'data-model-digest="{motif.model_digest}" data-match-start="{match.start}" '
        f'data-match-end="{match.end}" data-match-strand="{match.strand}"'
        + (
            f' data-score-ceiling="{score_ceiling:.17g}"'
            if avoider and score_ceiling is not None
            else ""
        )
        + ">",
        text(20, top + 17, model_name, size=12, weight=650),
        text(20, top + 37, f"{motif.width} nt · {match.strand} · {role}", fill=MUTED),
        text(
            20,
            top + 57,
            f"{score_label} {match.normalized_score:.4g}",
            size=12,
            fill=MUTED,
        ),
        text(20, top + 77, f"LLR {match.raw_score:.4g}", fill=MUTED),
        '<g class="information-axis">',
        f'<path d="M {left - 10} {logo_bottom - 72} h -4 v 72 h 4" fill="none" stroke="{INK}"/>',
        text(left - 18, logo_bottom + 4, "0", anchor="end", fill=MUTED),
        text(left - 18, logo_bottom - 68, "2 bits", anchor="end", fill=MUTED),
        "</g>",
        f'<line class="information-logo-baseline" x1="{match_left:.3f}" y1="{logo_bottom}" '
        f'x2="{match_left + match_width:.3f}" y2="{logo_bottom}" '
        f'stroke="{INK}" stroke-width="1"/>',
    ]
    for support in match.position_support:
        row = motif.probabilities[support.motif_position]
        information_bits = column_information(row)
        center_x = left + (support.candidate_position + 0.5) * cell
        column_bottom = float(logo_bottom)
        parts.append(
            f'<g class="information-logo-column" '
            f'data-motif-position="{support.motif_position}" '
            f'data-candidate-position="{support.candidate_position}" '
            f'data-information-bits="{information_bits:.17g}" '
            f'data-observed-base="{support.observed_base}">'
        )
        for base, probability in sorted(
            zip(_ALPHABET, row, strict=True), key=lambda item: (item[1], item[0])
        ):
            parts.append(
                _letter(
                    base=base,
                    probability=probability,
                    information_bits=information_bits,
                    observed_base=support.observed_base,
                    color=color,
                    center_x=center_x,
                    bottom_y=column_bottom,
                    width=cell * 0.8,
                    glyph_id=f"logo-{model_name}-{support.motif_position}-{base}",
                )
            )
            column_bottom -= probability * information_bits * PIXELS_PER_BIT
        parts.append("</g>")
    if limiting:
        marker_y = top + 2
        parts.extend(
            [
                f'<path class="limiting-marker" d="M {match_left:.3f} {marker_y:.3f} '
                f'v -5 h {match_width:.3f} v 5" fill="none" stroke="{INK}" '
                'stroke-width="2"/>',
                text(
                    20,
                    top + 117,
                    "LIMITING",
                    size=12,
                    weight=700,
                    fill=INK,
                ),
            ]
        )
    if avoider:
        parts.append(text(20, top + 97, f"ceiling {score_ceiling:.4g}", fill=MUTED))
        parts.append(
            f'<rect class="avoidance-ceiling-outline" x="{match_left:.3f}" y="{top + 21}" '
            f'width="{match_width:.3f}" height="{logo_bottom - top - 15:.3f}" '
            f'fill="none" stroke="{color}" stroke-width="1.5" '
            f'stroke-dasharray="6 4" data-score-ceiling="{score_ceiling:.17g}"/>'
        )
    elif match.spec_direction == "avoid" and match.spec_satisfaction is not None:
        parts.append(text(20, top + 97, f"satisfaction {match.spec_satisfaction:.4g}", fill=MUTED))
    parts.append("</g>")
    return "".join(parts)
