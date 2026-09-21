"""Threshold-free relationships among labeled selected motif intervals.

Maintainer(s): Eric J. South, Dunlop Lab
"""

from typing import Annotated, Literal

from pydantic import Field

from .evaluation import Evaluation

TopologyKey = tuple[
    tuple[
        str,
        Annotated[int, Field(strict=True, ge=0)],
        Annotated[int, Field(strict=True, gt=0)],
        Literal["+", "-"],
    ],
    ...,
]


def topology_key(evaluation: Evaluation, *, both: bool) -> TopologyKey:
    """Preserve endpoint order/equality and strand, quotienting valid symmetries.

    Endpoint ranks encode disjointness, touching, crossing, containment and
    coincidence for every labeled pair, including larger motif sets. They do
    not encode the sizes of gaps or overlaps; the original matches retain those.
    Selected sites are transformed, never rescanned or replaced by another tie.
    """
    if len(evaluation.matches) < 2:
        raise ValueError("architecture topology requires at least two selected matches")
    matches = sorted(evaluation.matches, key=lambda match: match.motif_id)
    length = len(evaluation.sequence)
    keys = []
    for reverse in (False, True) if both else (False,):
        sites = [
            (
                match.motif_id,
                length - match.end if reverse else match.start,
                length - match.start if reverse else match.end,
                ("-" if match.strand == "+" else "+") if reverse else match.strand,
            )
            for match in matches
        ]
        ranks = {
            position: rank
            for rank, position in enumerate(sorted({p for _, a, b, _ in sites for p in (a, b)}))
        }
        keys.append(tuple((name, ranks[a], ranks[b], strand) for name, a, b, strand in sites))
    return min(keys)
