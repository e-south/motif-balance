from __future__ import annotations

from dataclasses import dataclass

from ..model import InspectionCandidate, InspectionMatch

DNA_FONT_SIZE = 16
DNA_FONT_FAMILY = "Arial"
VISUAL_CONTRACT = "motif-balance.candidate-duplex/v2"


@dataclass(frozen=True)
class CandidateLayout:
    shown: tuple[InspectionMatch, ...]
    forward: tuple[InspectionMatch, ...]
    reverse: tuple[InspectionMatch, ...]
    cell: int
    left: int
    width: int
    logo_top: int
    logo_row_height: int
    primary_y: int
    complement_y: int
    reverse_logo_top: int
    height: int


def build_candidate_layout(
    candidate: InspectionCandidate,
    shown: tuple[InspectionMatch, ...],
) -> CandidateLayout:
    """Lay out molecular lanes; exact per-base score tables belong to JSON/HTML."""

    forward = tuple(match for match in shown if match.strand == "+")
    reverse = tuple(match for match in shown if match.strand == "-")
    cell = 24
    left = max(180, max((len(match.motif_id) for match in shown), default=0) * 8 + 40)
    width = max(600, left + len(candidate.sequence) * cell + 42)
    logo_top = 86
    logo_row_height = 142
    primary_y = logo_top + logo_row_height * len(forward) + 12
    complement_y = primary_y + 32
    reverse_logo_top = complement_y + 48
    height = reverse_logo_top + logo_row_height * len(reverse) + 28
    return CandidateLayout(
        shown=shown,
        forward=forward,
        reverse=reverse,
        cell=cell,
        left=left,
        width=width,
        logo_top=logo_top,
        logo_row_height=logo_row_height,
        primary_y=primary_y,
        complement_y=complement_y,
        reverse_logo_top=reverse_logo_top,
        height=height,
    )
