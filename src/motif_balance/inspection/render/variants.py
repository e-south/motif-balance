"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/inspection/render/variants.py

Render supplied diversification records without scoring or modifying sequences.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from html import escape

from motif_balance.model.variants import Substitution, VariantLibrary


def render_variant_map(library: VariantLibrary) -> str:
    """Align the parent duplex, selected sites, and single-substitution decisions."""
    length = len(library.parent.sequence)
    step = 32
    left = 210
    width = max(900, left + step * length + 32)
    desired = [m for m in library.parent.matches if m.spec_direction == "seek"]
    matrix_y = 150 + 28 * len(desired)
    height = matrix_y + 200
    rows = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<g font-family="Arial,sans-serif" fill="#24393e">',
    ]

    def text(x: float, y: float, value: str, size: int = 12) -> None:
        rows.append(f'<text x="{x}" y="{y}" font-size="{size}">{escape(value)}</text>')

    text(20, 28, "Single substitutions and jointly checked nucleotide options", 18)
    text(
        20,
        49,
        f"Encoded sequence count {library.encoded_sequence_count} · "
        f"per-model loss limit {library.max_score_loss:g}",
        13,
    )
    for i, m in enumerate(desired):
        y = 68 + 28 * i
        text(20, y + 13, f"{m.motif_id} {m.strand}  q={m.normalized_score:.3f}")
        rows.append(
            f'<rect x="{left + step * m.start}" y="{y}" '
            f'width="{step * (m.end - m.start) - 2}" height="19" rx="3" fill="#93b9b1"/>'
        )
        # The interval is in forward-reference coordinates; the strand label identifies it.
    duplex_y = 90 + 28 * len(desired)
    text(20, duplex_y, "Parent 5\u2032 → 3\u2032")
    text(20, duplex_y + 23, "Complement 3\u2032 → 5\u2032")
    complement = library.parent.sequence.translate(str.maketrans("ACGT", "TGCA"))
    for i, (base, opposite) in enumerate(zip(library.parent.sequence, complement, strict=True)):
        x = left + i * step + 10
        text(x, duplex_y, base, 14)
        text(x, duplex_y + 23, opposite, 14)
        rows.append(f'<path d="M{x + 5},{duplex_y + 4}v5" stroke="#9da8aa"/>')
    substitutions: dict[tuple[int, str], Substitution] = {
        (s.position, s.base): s for s in library.substitutions
    }
    for row, base in enumerate("ACGT"):
        y = matrix_y + row * 28
        text(left - 25, y + 18, base, 14)
        for position in range(length):
            s = substitutions.get((position, base))
            is_parent = base == library.parent.sequence[position]
            retained = base in library.allowed_bases[position]
            fill = (
                "#89b5a7"
                if retained
                else "#ead7af"
                if s and s.status == "passes_alone"
                else "#f0f1f1"
            )
            x = left + step * position
            tooltip = (
                "Parent base"
                if is_parent
                else "Not editable"
                if s is None
                else (
                    s.status.replace("_", " ")
                    + "; "
                    + "; ".join(
                        f"{m.motif_id} component change {delta:+.5f}, "
                        f"site [{m.start},{m.end}) {m.strand}"
                        for m, delta in zip(s.evaluation.matches, s.component_changes, strict=True)
                    )
                )
            )
            rows.append(
                f'<rect x="{x}" y="{y}" width="30" height="25" fill="{fill}">'
                f"<title>{escape(tooltip)}</title></rect>"
            )
            value = (
                "•"
                if is_parent
                else "\u00d7"
                if s and s.changed_desired_sites
                else (f"{max(0.0, -min(s.component_changes)):.2f}" if s else "")
            )
            text(x + 2, y + 17, value, 10)
    text(20, matrix_y + 136, "Jointly retained options", 12)
    for position, _bases in enumerate(library.allowed_bases):
        text(left + step * position + 4, matrix_y + 136, library.template[position], 13)
    text(
        20,
        matrix_y + 161,
        "Green = jointly checked options (• parent). Sand = passes alone, not retained.",
    )
    text(
        20,
        matrix_y + 180,
        "Cell values = largest adverse component change. \u00d7 = selected site changes. "
        "Gray = rejected or outside editable positions.",
    )
    rows.append("</g></svg>")
    return "".join(rows)
