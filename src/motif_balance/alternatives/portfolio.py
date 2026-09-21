"""Score a supplied pool and select an explicitly constrained full portfolio.

Maintainer(s): Eric J. South, Dunlop Lab
"""

from __future__ import annotations

from itertools import combinations

from motif_balance.compile import compile_scoring
from motif_balance.constants import MAX_ARCHITECTURE_DISTANCE_PAIRS, MAX_ARCHITECTURE_PREPARED_PAIRS
from motif_balance.model import DesignSpec, candidate_id_for_sequence
from motif_balance.model.alternatives import architecture_key
from motif_balance.model.base import _sha256
from motif_balance.model.selection import (
    PortfolioMember,
    PortfolioPolicy,
    PortfolioSelection,
    PortfolioSeparation,
    portfolio_architecture_bound,
    portfolio_distance_work,
)
from motif_balance.scoring import evaluate
from motif_balance.selection import _bottleneck_subset

from .geometry import pair_separation, prepare_distances
from .pool import prepare_pool


def select_portfolio(
    sequences: tuple[str, ...] | list[str], spec: DesignSpec, policy: PortfolioPolicy
) -> PortfolioSelection:
    """Rescore canonical literals; select unchanged evaluations, never class winners.

    The saved generation request is not rewritten to the selection count. No
    generation takes place, and infeasibility is scoped to this pool unless the
    necessary pair-architecture bound itself rules out the requested count.
    """
    if not isinstance(policy, PortfolioPolicy):
        raise ValueError("portfolio selection requires a current typed portfolio policy")
    policy = PortfolioPolicy.model_validate(policy.model_dump())
    pool = prepare_pool(sequences, spec)
    both = spec.strands == "both"
    if (policy.equivalence == "reverse_complement") != both:
        raise ValueError("portfolio equivalence must match the scoring strand policy")
    canonical = pool.canonical_sequences
    # Width and whole-model validity are checked even when a necessary bound
    # can refuse the portfolio before candidate scoring.
    problem = compile_scoring(spec)
    bound = portfolio_architecture_bound(spec)
    impossible = policy.architectures == "distinct" and bound is not None and policy.count > bound
    common = {
        "spec": spec,
        "policy": policy,
        "problem_id": problem.problem_id,
        "request_digest": _sha256(spec.model_dump(mode="json")),
        "pool_digest": pool.digest,
        "input_records": len(pool.sequences),
        "literal_sequences": pool.literal_count,
        "sequence_classes": len(canonical),
        "architecture_upper_bound": bound,
    }
    if impossible:
        return PortfolioSelection.model_validate(
            {
                **common,
                "status": "architecture_bound",
                "scoring_evaluations": 0,
                "distance_base_operations": 0,
                "selection_work": 0,
                "members": (),
                "separations": (),
                "quality": None,
                "minimum_separation": None,
            }
        )
    pair_work = policy.count > 1 and len(canonical) >= policy.count
    pairs, operations, prepared_pairs = portfolio_distance_work(len(canonical), spec, policy.count)
    if (
        operations > policy.distance_base_budget
        or pairs > MAX_ARCHITECTURE_DISTANCE_PAIRS
        or prepared_pairs > MAX_ARCHITECTURE_PREPARED_PAIRS
    ):
        raise ValueError("portfolio selection exceeds the distance-comparison limit")
    ranked = tuple(
        sorted(
            (evaluate(s, problem) for s in canonical), key=lambda e: (-e.balance_score, e.sequence)
        )
    )
    geometries = tuple(architecture_key(e, both=both) for e in ranked)
    prepared = tuple(prepare_distances(e) for e in ranked) if pair_work else ()
    edges = [0] * len(ranked)
    # One bounded bitset per candidate: quadratic bits, not a float matrix.
    for i, prepared_left in enumerate(prepared):
        for j in range(i + 1, len(prepared)):
            if policy.architectures == "distinct" and geometries[i] == geometries[j]:
                continue
            distance, _ = pair_separation(
                prepared_left, prepared[j], both=both, kind=policy.separation
            )
            if distance + 1e-12 >= policy.min_distance:
                edges[i] |= 1 << j
    subset = _bottleneck_subset(
        ranked, tuple(edges), count=policy.count, work_limit=policy.work_limit
    )
    members = tuple(
        PortfolioMember(
            candidate_id=candidate_id_for_sequence(ranked[i].sequence),
            evaluation=ranked[i],
            architecture=geometries[i],
        )
        for i in subset.indices
    )
    separations = []
    for (i, left), (j, right) in combinations(zip(subset.indices, members, strict=True), 2):
        value, orientation = pair_separation(
            prepared[i], prepared[j], both=both, kind=policy.separation
        )
        separations.append(
            PortfolioSeparation(
                left_id=left.candidate_id,
                right_id=right.candidate_id,
                value=value,
                orientation=orientation,
            )
        )
    status = (
        ("optimal" if subset.complete else "feasible")
        if members
        else ("pool_infeasible" if subset.complete else "unresolved")
    )
    return PortfolioSelection.model_validate(
        {
            **common,
            "status": status,
            "scoring_evaluations": len(ranked),
            "distance_base_operations": operations,
            "selection_work": subset.work_used,
            "members": members,
            "separations": tuple(separations),
            "quality": min((m.evaluation.balance_score for m in members), default=None),
            "minimum_separation": min((s.value for s in separations), default=None),
        }
    )


def verify_portfolio_selection(
    result: PortfolioSelection, sequences: tuple[str, ...] | list[str]
) -> PortfolioSelection:
    """Replay from the explicit pool; parsing alone cannot verify scores or proofs."""
    if not isinstance(result, PortfolioSelection):
        raise ValueError("portfolio replay requires a current typed selection")
    replayed = select_portfolio(sequences, result.spec, result.policy)
    if replayed != result:
        raise ValueError("portfolio selection replay disagrees with the supplied record")
    return replayed
