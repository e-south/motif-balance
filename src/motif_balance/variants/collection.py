"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/variants/collection.py

Validate a whole selected collection before expanding any member.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from typing import Literal

from motif_balance.model.alternatives import CollectionReport
from motif_balance.model.variant_collection import CollectionVariants

from .api import _MAX_SCORE_OPERATIONS, _prepare, diversify


def diversify_collection(
    report: CollectionReport,
    *,
    min_balance: float | None = None,
    max_score_loss: float | None = None,
    max_variants: int = 256,
    editable_mask: tuple[bool, ...] | None = None,
    construction_order: Literal["least_loss", "greatest_loss", "hashed"] = "least_loss",
    max_total_score_operations: int = _MAX_SCORE_OPERATIONS,
) -> CollectionVariants:
    """Expand each delivered arrangement, retaining separate exact products.

    Every parent must be eligible. A collection with missing requested arrangements
    remains incomplete; diversification cannot supply another arrangement.
    Whole-collection admission precedes construction. Evaluations recorded by each
    library exclude this coordinator's parent-only verification scans.
    The total-work allowance controls sequential effort, not peak cache size or
    the output record limit. It does not change a member's construction settings.
    """
    if (
        type(max_total_score_operations) is not int
        or not 1 <= max_total_score_operations <= 16 * _MAX_SCORE_OPERATIONS
    ):
        raise ValueError("total work allowance must be an integer from 1 through 16 billion")
    report = CollectionReport.model_validate(report.model_dump(mode="python", warnings=False))
    members = report.collection.members
    if not members or len(members) > 16:
        raise ValueError("collection diversification requires 1 through 16 delivered members")
    upper_operations = upper_records = 0
    for rank, member in enumerate(members, 1):
        try:
            _, parent, positions, cost, upper, _ = _prepare(
                member.evaluation.sequence,
                report.ranking.spec,
                min_balance=min_balance,
                max_score_loss=max_score_loss,
                max_variants=max_variants,
                editable_mask=editable_mask,
                construction_order=construction_order,
            )
            if parent != member.evaluation:
                raise ValueError("saved parent does not match its rescored DNA")
            upper_operations += cost * upper
            upper_records += (max_variants + 3 * len(positions)) * len(parent.matches)
        except ValueError as exc:
            raise ValueError(f"collection member {rank}: {exc}") from exc
    if upper_operations > max_total_score_operations:
        raise ValueError(
            f"collection needs a conservative total work allowance of {upper_operations} "
            "positional score operations; reduce max_variants or explicitly raise "
            "max_total_score_operations"
        )
    if upper_records > 50_000:
        raise ValueError("collection exceeds 50,000 output match records; reduce max_variants")
    return CollectionVariants(
        source=report,
        libraries=tuple(
            diversify(
                member.evaluation.sequence,
                report.ranking.spec,
                min_balance=min_balance,
                max_score_loss=max_score_loss,
                max_variants=max_variants,
                editable_mask=editable_mask,
                construction_order=construction_order,
            )
            for member in members
        ),
    )
