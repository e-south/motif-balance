"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/variants/expansion_collection.py

Admit the whole collection before sequentially expanding its members.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from motif_balance.compile import compile_scoring
from motif_balance.model.alternatives import CollectionReport
from motif_balance.model.expanded_collection import ExpandedCollection
from motif_balance.scoring import evaluate

from .expansion import (
    MAX_CACHED_BASES,
    MAX_HANDOFF_BYTES,
    MAX_MATCH_RECORDS,
    MAX_OPERATIONS,
    _admit,
    _output_bound,
    expand,
)


def expand_collection(
    report: CollectionReport,
    *,
    min_balance: float,
    max_variants: int = 256,
    max_evaluations: int = 4096,
    editable_mask: tuple[bool, ...] | None = None,
    max_total_score_operations: int = MAX_OPERATIONS,
) -> ExpandedCollection:
    """Return separate explicit lists for each supplied arrangement.

    Parent verification precedes all construction. Its scans are coordinator
    overhead, separate from each member's recorded expansion evaluations.
    """
    if (
        type(max_total_score_operations) is not int
        or not 1 <= max_total_score_operations <= 16 * MAX_OPERATIONS
    ):
        raise ValueError("total work allowance must be an integer from 1 through 16 billion")
    report = CollectionReport.model_validate(report.model_dump(mode="python", warnings=False))
    members = report.collection.members
    if not 1 <= len(members) <= 16:
        raise ValueError("collection expansion requires 1 through 16 delivered members")
    spec = report.ranking.spec
    cost = _admit(spec, min_balance, max_variants, max_evaluations, editable_mask)
    if len(members) * max_evaluations * cost > max_total_score_operations:
        raise ValueError(
            "collection exceeds total work allowance; "
            "reduce evaluations or explicitly raise max_total_score_operations"
        )
    if (
        len(members) * max_evaluations * spec.length > MAX_CACHED_BASES
        or len(members) * max_variants * len(spec.specifications) > MAX_MATCH_RECORDS
        or len(members) * _output_bound(spec, max_variants, max_evaluations)
        + 8 * len(report.model_dump_json(indent=2).encode())
        > MAX_HANDOFF_BYTES
    ):
        raise ValueError(
            "collection exceeds bounded output records; reduce evaluations or variants"
        )
    problem = compile_scoring(spec)
    for rank, member in enumerate(members, 1):
        parent = evaluate(member.evaluation.sequence, problem)
        if parent != member.evaluation:
            raise ValueError(f"collection member {rank}: saved parent disagrees with rescoring")
        if parent.balance_score < min_balance - 1e-12:
            raise ValueError(f"collection member {rank}: parent is below the balance floor")
    return ExpandedCollection(
        source=report,
        libraries=tuple(
            expand(
                member.evaluation.sequence,
                spec,
                min_balance=min_balance,
                max_variants=max_variants,
                max_evaluations=max_evaluations,
                editable_mask=editable_mask,
            )
            for member in members
        ),
    )
