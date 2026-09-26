"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/playback/duplex.py

Draw compact strand-aligned DNA and information logos from inspected matches.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

import math

from motif_balance.errors import ArtifactError
from motif_balance.inspection.model import InspectionCandidate, InspectionMatch, InspectionProblem
from motif_balance.inspection.render.candidate_projection import validate_candidate_projection
from motif_balance.inspection.render.logo_shapes import (
    PIXELS_PER_BIT,
    information_bits,
    information_letter,
)
from motif_balance.inspection.render.svg_primitives import safe_text

COLORS = ("#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#332288", "#666666")
FONT = 18
CELL = 20
LANE = 98


def label(x: float, y: float, value: str, *, anchor: str = "start", color: str = "#252525") -> str:
    return (
        f'<text x="{x:g}" y="{y:g}" font-family="Arial,sans-serif" font-size="{FONT}" '
        f'text-anchor="{anchor}" fill="{color}">{safe_text(value)}</text>'
    )


def left_margin(problem: InspectionProblem) -> int:
    """Leave room for the longest exact motif identifier at the leftmost window."""
    return max(
        105,
        max(
            len(motif.motif_id) + (8 if motif.direction == "avoid" else 0)
            for motif in problem.motifs
        )
        * 11
        + 18,
    )


def _logo(
    problem: InspectionProblem, match: InspectionMatch, *, left: int, baseline: int, color: str
) -> list[str]:
    motif = next(m for m in problem.motifs if m.motif_id == match.motif_id)
    if any(not math.isclose(p, 0.25, abs_tol=1e-12) for p in motif.background):
        raise ArtifactError("information-logo playback requires a uniform scoring background")
    upward = match.strand == "+"
    parts = []
    for support in match.position_support:
        row = motif.probabilities[support.motif_position]
        bits = information_bits(row)
        offset = 0.0
        for base, probability in sorted(
            zip("ACGT", row, strict=True), key=lambda item: (item[1], item[0])
        ):
            height = probability * bits * PIXELS_PER_BIT
            # Reverse-strand stacks grow down from zero, while every letter stays upright.
            bottom = baseline - offset if upward else baseline + offset + height
            parts.append(
                information_letter(
                    base=base,
                    probability=probability,
                    bits=bits,
                    color=color if base == support.observed_base else "#D1D5DB",
                    center_x=left + (support.candidate_position + 0.5) * CELL,
                    bottom_y=bottom,
                    width=CELL * 0.84,
                    glyph_id=f"logo-{safe_text(match.motif_id)}-{support.motif_position}-{base}",
                    observed=base == support.observed_base,
                )
            )
            offset += height
    return parts


def render_duplex(
    problem: InspectionProblem,
    candidate: InspectionCandidate,
    *,
    top_lanes: int,
) -> str:
    """Keep coordinates literal; logo probabilities and observed bases share one strand frame."""
    validate_candidate_projection(problem, candidate)
    left = left_margin(problem)
    primary = 36 + top_lanes * LANE
    complement = primary + 30
    motif_order = {motif.motif_id: i for i, motif in enumerate(problem.motifs)}
    parts = []
    # Gray saturation reports the highest relative positional support among the
    # displayed matches at each coordinate, on either complementary strand.
    support_by_position: dict[int, float] = {}
    for match in candidate.matches:
        motif = next(m for m in problem.motifs if m.motif_id == match.motif_id)
        for support in match.position_support:
            row = motif.probabilities[support.motif_position]
            high = max(row)
            strength = support.model_probability / high if high else 0.0
            position = support.candidate_position
            support_by_position[position] = max(support_by_position.get(position, 0.0), strength)
    for sequence, baseline, primes in (
        (candidate.sequence, primary, ("5\u2032", "3\u2032")),
        (candidate.complement_sequence, complement, ("3\u2032", "5\u2032")),
    ):
        parts.append(label(left - 12, baseline + 6, primes[0], anchor="end"))
        for i, base in enumerate(sequence):
            shade = round(170 - 140 * support_by_position.get(i, 0.0))
            parts.append(
                label(
                    left + (i + 0.5) * CELL,
                    baseline + 6,
                    base,
                    anchor="middle",
                    color=f"#{shade:02x}{shade:02x}{shade:02x}",
                )
            )
        parts.append(label(left + problem.length * CELL + 12, baseline + 6, primes[1]))
    for i in range(problem.length):
        x = left + (i + 0.5) * CELL
        parts.append(f'<path d="M{x:g} {primary + 12} v6" stroke="#C9CDD1"/>')
    lanes = {"+": 0, "-": 0}
    for match in sorted(candidate.matches, key=lambda m: m.motif_id):
        lane = lanes[match.strand]
        lanes[match.strand] += 1
        color = "#467A6F" if len(problem.motifs) > 8 else COLORS[motif_order[match.motif_id]]
        x = left + match.start * CELL
        width = (match.end - match.start) * CELL
        y = primary - 32 - lane * LANE if match.strand == "+" else complement + 14 + lane * LANE
        zero = y if match.strand == "+" else y + 20
        parts.append(
            f'<g data-motif-id="{safe_text(match.motif_id)}" data-strand="{match.strand}" '
            f'data-start="{match.start}" data-end="{match.end}">'
        )
        parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="20" rx="3" fill="{color}"/>')
        for support in match.position_support:
            parts.append(
                label(
                    left + (support.candidate_position + 0.5) * CELL,
                    y + 16,
                    support.observed_base,
                    anchor="middle",
                    color="#FFFFFF",
                )
            )
        name = match.motif_id + (" (avoid)" if match.spec_direction == "avoid" else "")
        parts.append(label(x - 7, y + 16, name, anchor="end", color=color))
        parts.append(label(x + width + 7, y + 16, f"q={match.normalized_score:.2f}", color=color))
        # Large sets share the same logo scale; repeated axes obscure the placements.
        if len(problem.motifs) <= 8:
            axis_x = x - 8
            direction = -1 if match.strand == "+" else 1
            parts.append(
                f'<path d="M{axis_x} {zero} h-4 v{direction * 72} h4" fill="none" stroke="#777"/>'
            )
            parts.append(
                label(
                    axis_x - 9,
                    zero + (-5 if direction == -1 else 20),
                    "0",
                    anchor="end",
                    color="#666",
                )
            )
            parts.append(
                label(axis_x - 9, zero + direction * 72 + 6, "2", anchor="end", color="#666")
            )
        parts.extend(_logo(problem, match, left=left, baseline=zero, color=color))
        parts.append("</g>")
    return "".join(parts)
