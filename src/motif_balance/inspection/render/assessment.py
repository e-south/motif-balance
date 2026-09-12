"""Display one inspected arrangement without rescoring models or drawing a candidate."""

from __future__ import annotations

from ..assessment.model import PairAssessmentInspection
from ..limits import MAX_SVG_ASSESSMENT_LENGTH
from .logo_shapes import PIXELS_PER_BIT, information_bits, information_letter
from .svg_primitives import INK, MUTED, finish_svg, motif_color, motif_id, svg_start, text


def render_pair_assessment_svg(inspection: PairAssessmentInspection) -> bytes:
    """Render pre-search local-conflict evidence in one common physical base frame.

    Use inspect_pair_assessment to construct this record from explicit models.
    Structural consistency here is not independent validation of external scores.
    """
    if not isinstance(inspection, PairAssessmentInspection):
        raise ValueError("pair assessment rendering requires its inspected projection")
    view = PairAssessmentInspection.model_validate_json(inspection.model_dump_json())
    result = view.assessment
    if result.length > MAX_SVG_ASSESSMENT_LENGTH:
        raise ValueError(
            f"assessment SVG supports at most {MAX_SVG_ASSESSMENT_LENGTH} nt; use inspection JSON"
        )
    left = max(160, max(len(m.motif_id) for m in view.motifs) * 8 + 40)
    cell, width = 24, max(620, left + 24 * result.length + 40)
    parts = svg_start(
        width=width,
        height=400,
        title_id="assessment-title",
        desc_id="assessment-desc",
        view_id="pair-assessment-view",
    )
    parts.extend(
        [
            '<title id="assessment-title">Model preferences before sequence search</title>',
            '<desc id="assessment-desc">One legal motif arrangement; not a designed sequence. '
            "Both logos use top-strand base coordinates. Orange exclamation marks show "
            "positive local conflict; green equals signs show zero local conflict.</desc>",
            f'<rect width="{width}" height="400" fill="white"/>',
            text(20, 27, "Model preferences before sequence search", size=18, weight=700),
            text(
                20,
                53,
                f"L = {result.length} nt · local-conflict score {result.structural_score:.4f} · "
                f"{result.arrangement_count} arrangements",
                size=13,
            ),
        ]
    )
    for column in view.columns:
        if column.kind == "unshared":
            continue
        color = "#F6DAB5" if column.kind == "conflict" else "#E5F0E9"
        parts.append(
            f'<rect class="shared-column" data-coordinate="{column.coordinate}" '
            f'data-kind="{column.kind}" x="{left + cell * column.coordinate}" '
            f'y="78" width="{cell}" height="210" fill="{color}"/>'
        )
        parts.append(
            text(
                left + cell * (column.coordinate + 0.5),
                312,
                "!" if column.kind == "conflict" else "=",
                anchor="middle",
                weight=700,
            )
        )
    arrangement = result.best_arrangement
    for index, model in enumerate(view.motifs):
        name, baseline = motif_id(model.motif_id), 154 + 130 * index
        strand = "+" if index == 0 else arrangement.right_strand
        color = motif_color(model.motif_id)
        parts.append(
            f'<g class="assessment-logo" data-motif-id="{name}" '
            f'data-model-digest="{model.model_digest}" data-strand="{strand}" '
            'data-base-frame="top-strand">'
        )
        parts.append(text(20, baseline - 48, name, weight=700))
        parts.append(text(20, baseline - 28, f"{model.width} nt · {strand}", fill=MUTED))
        parts.append(
            f'<path d="M {left - 10} {baseline - 72} h -4 v 72 h 4" fill="none" stroke="{INK}"/>'
        )
        parts.append(text(left - 20, baseline - 68, "2 bits", anchor="end", fill=MUTED))
        parts.append(text(left - 20, baseline + 4, "0", anchor="end", fill=MUTED))
        for column in view.columns:
            position = column.left_position if index == 0 else column.right_position
            if position is None:
                continue
            row = model.probabilities[position]
            if strand == "-":
                row = (row[3], row[2], row[1], row[0])
            bits, bottom = information_bits(row), float(baseline)
            parts.append(
                f'<g class="assessment-logo-column" data-coordinate="{column.coordinate}" '
                f'data-motif-position="{position}" data-information-bits="{bits:.17g}">'
            )
            for base, probability in sorted(
                zip("ACGT", row, strict=True), key=lambda p: (p[1], p[0])
            ):
                parts.append(
                    information_letter(
                        base=base,
                        probability=probability,
                        bits=bits,
                        color=color,
                        center_x=left + cell * (column.coordinate + 0.5),
                        bottom_y=bottom,
                        width=cell * 0.8,
                        glyph_id=f"assessment-{index}-{position}-{base}",
                    )
                )
                bottom -= probability * bits * PIXELS_PER_BIT
            parts.append("</g>")
        parts.append("</g>")
    for i in range(result.length):
        parts.append(text(left + cell * (i + 0.5), 336, i + 1, anchor="middle", fill=MUTED))
    parts.extend(
        [
            text(
                20,
                360,
                "! Positive local conflict   = Zero local conflict   Blank: no overlap",
                size=12,
            ),
            text(
                20,
                382,
                "Top-strand coordinates; reverse motifs are complemented. Not a designed sequence.",
                size=12,
                fill=MUTED,
            ),
            "</svg>",
        ]
    )
    return finish_svg(parts)
