"""Selected-site equivalence and separate, label-invariant pair distances."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from motif_balance.model import Evaluation
from motif_balance.scoring import reverse_complement


@dataclass(frozen=True, slots=True)
class _PreparedDistances:
    length: int
    context: tuple[tuple[str, int, str | None], ...]
    base_mask: int
    sequence: int
    footprint: int
    reverse_sequence: int
    reverse_footprint: int
    separations: tuple[int, ...]
    relative_strands: int


def _pack(sequence: str) -> int:
    # Two bits per base; the low bit of each pair later marks a mismatch.
    codes = {"A": 0, "C": 1, "G": 2, "T": 3}
    return sum(codes[base] << (2 * index) for index, base in enumerate(sequence))


def prepare_distances(evaluation: Evaluation) -> _PreparedDistances:
    """Prepare one already evaluated candidate; no scoring or orientation choice."""
    length = len(evaluation.sequence)
    if len(evaluation.matches) < 2:
        raise ValueError("distance context requires at least two selected matches")
    footprint, reverse_footprint = 0, 0
    for match in evaluation.matches:
        width = match.end - match.start
        # OR preserves overlapping footprints without double-counting positions.
        span = ((1 << (2 * width)) - 1) // 3
        footprint |= span << (2 * match.start)
        reverse_footprint |= span << (2 * (length - match.end))
    pairs = tuple(combinations(evaluation.matches, 2))
    return _PreparedDistances(
        length=length,
        context=tuple((m.motif_id, m.end - m.start, m.spec_direction) for m in evaluation.matches),
        base_mask=((1 << (2 * length)) - 1) // 3,
        sequence=_pack(evaluation.sequence),
        footprint=footprint,
        reverse_sequence=_pack(reverse_complement(evaluation.sequence)),
        reverse_footprint=reverse_footprint,
        separations=tuple(abs(a.start + a.end - b.start - b.end) for a, b in pairs),
        relative_strands=sum((a.strand == b.strand) << index for index, (a, b) in enumerate(pairs)),
    )


def pair_distances(
    left: _PreparedDistances, right: _PreparedDistances, *, both: bool
) -> tuple[float, float, float, float]:
    """Exact same metrics using request-local, prepared candidate representations."""
    if left.length != right.length or left.context != right.context:
        raise ValueError("pair distances require the same length and selected-match context")
    options = [(right.sequence, right.footprint)]
    if both:
        options.append((right.reverse_sequence, right.reverse_footprint))
    sequence_distances = []
    for sequence, sites in options:
        differences = left.sequence ^ sequence
        mismatches = (differences | (differences >> 1)) & left.base_mask
        covered = left.footprint | sites
        sequence_distances.append(
            (
                mismatches.bit_count() / left.length,
                (mismatches & covered).bit_count() / covered.bit_count(),
            )
        )
    # Choose one common orientation by whole-sequence distance, then footprint
    # on a tie; do not independently optimize each component's orientation.
    sequence_distance, footprint = min(sequence_distances)
    count = len(left.separations)
    spacing = sum(abs(a - b) for a, b in zip(left.separations, right.separations, strict=True))
    orientation = (left.relative_strands ^ right.relative_strands).bit_count()
    return sequence_distance, footprint, spacing / (2 * count), orientation / count
