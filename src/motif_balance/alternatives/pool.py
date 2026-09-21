"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/alternatives/pool.py

Shared pool contract for architecture ranking and constrained selection.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass

from motif_balance.constants import (
    MAX_ARCHITECTURE_POOL_RECORDS,
    MAX_PORTFOLIO_BASES,
    MAX_SCORE_BASE_OPERATIONS,
)
from motif_balance.model import DesignSpec
from motif_balance.model.alternatives import validate_architecture_spec
from motif_balance.model.base import _sha256
from motif_balance.scoring import reverse_complement


@dataclass(frozen=True, slots=True)
class SuppliedPool:
    """Preserve input multiplicity separately from canonical sequences to score."""

    sequences: tuple[str, ...]
    canonical_sequences: tuple[str, ...]
    literal_count: int
    digest: str


def _admit(sequences: tuple[str, ...] | list[str], spec: DesignSpec) -> tuple[str, ...]:
    validate_architecture_spec(spec)
    if not isinstance(sequences, (tuple, list)) or len(sequences) > MAX_ARCHITECTURE_POOL_RECORDS:
        raise ValueError("sequence pool must be a bounded tuple or list of at most 50,000 records")
    if len(sequences) * spec.length > MAX_PORTFOLIO_BASES:
        raise ValueError("sequence pool exceeds the total-base limit")
    supplied = tuple(sequences)
    if any(
        not isinstance(s, str) or len(s) != spec.length or set(s) - set("ACGT") for s in supplied
    ):
        raise ValueError("each supplied sequence must be uppercase fixed-length A/C/G/T DNA")
    operations = len(set(supplied)) * sum(
        (spec.length - item.motif.width + 1)
        * item.motif.width
        * (2 if spec.strands == "both" else 1)
        for item in spec.specifications
    )
    if operations > MAX_SCORE_BASE_OPERATIONS:
        raise ValueError("sequence pool exceeds the scoring-operation limit")
    return supplied


def prepare_pool(sequences: tuple[str, ...] | list[str], spec: DesignSpec) -> SuppliedPool:
    """Check the complete pool before scoring and choose one literal per duplex."""
    supplied = _admit(sequences, spec)
    literals = set(supplied)
    both = spec.strands == "both"
    # Canonicalization precedes scoring so supplying the opposite strand cannot
    # change which equally scoring match is chosen by the coordinate tie rule.
    canonical = tuple(sorted({min(s, reverse_complement(s)) if both else s for s in literals}))
    return SuppliedPool(
        sequences=supplied,
        canonical_sequences=canonical,
        literal_count=len(literals),
        digest=_sha256(sorted(supplied)),
    )
