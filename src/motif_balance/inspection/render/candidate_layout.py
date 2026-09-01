from __future__ import annotations

from dataclasses import dataclass

from ..model import InspectionCandidate, InspectionMatch

_MONOSPACE_CHARACTER_WIDTH = 8
_CELL_HORIZONTAL_PADDING = 12


def support_label(value: float) -> str:
    return f"{value:+.2g}"


def _candidate_cell_width(shown: tuple[InspectionMatch, ...]) -> int:
    """Keep exact support labels readable, even for realistic long motifs."""

    labels = tuple(
        support_label(support.llr_contribution)
        for match in shown
        for support in match.position_support
    )
    longest_label = max((len(label) for label in labels), default=0)
    label_width = longest_label * _MONOSPACE_CHARACTER_WIDTH + _CELL_HORIZONTAL_PADDING
    return max(44, label_width)


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
    support_y: int
    height: int


def build_candidate_layout(
    candidate: InspectionCandidate,
    shown: tuple[InspectionMatch, ...],
) -> CandidateLayout:
    """Derive deterministic geometry without changing projected scientific state."""

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
        support_y=support_y,
        height=height,
    )
