"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/inspection/render/compact.py

Draw the DNA, selected sites, motif preferences, and normalized scores together.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from ..model import InspectionCandidate, InspectionProblem
from .candidate_layout import CandidateLayout
from .candidate_projection import shown_matches, validate_candidate_projection
from .candidate_sections import _duplex, _match_lane
from .information_logo import render_coordinate_aligned_information_logo
from .svg_primitives import finish_svg, motif_color, safe_text, text


def render_compact_candidate_svg(
    problem: InspectionProblem, candidate: InspectionCandidate
) -> bytes:
    """Use the existing projection and glyphs, without detailed scoring annotations."""
    validate_candidate_projection(problem, candidate)
    matches = shown_matches(candidate)
    forward = tuple(m for m in matches if m.strand == "+")
    reverse = tuple(m for m in matches if m.strand == "-")
    cell, row = 24, 132
    left = max(196, max(len(m.motif_id) for m in matches) * 10 + 125)
    width = max(540, left + problem.length * cell + 44)
    primary_y = 24 + row * len(forward) + 16
    complement_y = primary_y + 30
    reverse_top = complement_y + 44
    height = reverse_top + row * len(reverse) + 34
    layout = CandidateLayout(
        matches,
        forward,
        reverse,
        cell,
        left,
        width,
        24,
        row,
        primary_y,
        complement_y,
        reverse_top,
        height,
    )
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'role="img" aria-labelledby="candidate-title candidate-desc">',
        '<title id="candidate-title">DNA and its selected motif matches</title>',
        '<desc id="candidate-desc">',
        safe_text(
            f"Sequence {candidate.sequence}. Balance {candidate.balance_score:.6g}. "
            "Each q is the motif's best normalized match. Logos show information in bits. "
            "Filled windows show the selected bases on the corresponding strand."
        ),
        "</desc>",
        f'<rect width="{width}" height="{height}" fill="white"/>',
    ]
    motifs = {m.motif_id: m for m in problem.motifs}
    for lanes, origin in ((forward, layout.logo_top), (reverse, reverse_top)):
        for index, match in enumerate(lanes):
            top = origin + index * row
            window = top + 100 if match.strand == "+" else top - 24
            parts.append(
                render_coordinate_aligned_information_logo(
                    motifs[match.motif_id],
                    match,
                    top=top,
                    left=left,
                    cell=cell,
                    limiting=False,
                    compact=True,
                )
            )
            parts.append(_match_lane(match, top=window, layout=layout))
            role = " (avoid)" if match.spec_direction == "avoid" else ""
            parts.append(
                text(
                    16,
                    window + 15,
                    f"{match.motif_id}{role}  q = {match.normalized_score:.3f}",
                    size=16,
                    fill=motif_color(match.motif_id),
                    weight=650,
                )
            )
    parts.extend(_duplex(candidate, layout))
    components = ", ".join(
        f"1 \u2212 {m.normalized_score:.3f}"
        if m.spec_direction == "avoid"
        else f"{m.normalized_score:.3f}"
        for m in candidate.matches
    )
    balance = f"Balance B = {candidate.balance_score:.3f}"
    if len(matches) <= 4:
        balance = f"Balance B = min({components}) = {candidate.balance_score:.3f}"
    parts.extend([text(width / 2, height - 14, balance, size=18, anchor="middle"), "</svg>\n"])
    return finish_svg(parts)
