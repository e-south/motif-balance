from __future__ import annotations


class MotifBalanceError(RuntimeError):
    """Base class for stable, user-facing Motif Balance failures."""

    code = "motif_balance_error"

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        motif_id: str | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.field = field
        self.motif_id = motif_id
        self.hint = hint


class InvalidMotif(MotifBalanceError):
    code = "invalid_motif"


class InvalidDesign(MotifBalanceError):
    code = "invalid_design"


class InvalidSequence(MotifBalanceError):
    code = "invalid_sequence"


class IncompatibleDesign(MotifBalanceError):
    code = "incompatible_design"


class SearchBudgetExhausted(MotifBalanceError):
    """Search ended without enough unique evaluated candidates."""

    code = "search_budget_exhausted"

    def __init__(
        self,
        *,
        requested_count: int,
        valid_count: int,
        evaluations_used: int,
        best_score: float | None,
        hint: str = "Increase evaluations or reduce the requested candidate count.",
    ) -> None:
        message = (
            f"Search used {evaluations_used} evaluator calls but produced only {valid_count} "
            f"unique candidates for a requested portfolio of {requested_count}. "
            "No portfolio was published."
        )
        super().__init__(message, field="count", hint=hint)
        self.requested_count = requested_count
        self.valid_count = valid_count
        self.evaluations_used = evaluations_used
        self.best_score = best_score


class ConstraintFeasibilityExhausted(MotifBalanceError):
    """A bounded search ended before enough constraint-feasible sequences were found."""

    code = "constraint_feasibility_exhausted"

    def __init__(
        self,
        *,
        requested_count: int,
        feasible_count: int,
        evaluations_used: int,
        best_max_excess: float | None,
    ) -> None:
        super().__init__(
            f"Search used {evaluations_used} evaluator calls but found only {feasible_count} "
            f"constraint-feasible sequences for a requested portfolio of {requested_count}. "
            "No portfolio was published. This does not establish that the hard avoidance "
            "constraints are infeasible in the complete DNA design space.",
            field="avoiders",
            hint="Increase evaluations or revise the declared hard constraints.",
        )
        self.requested_count = requested_count
        self.feasible_count = feasible_count
        self.evaluations_used = evaluations_used
        self.best_max_excess = best_max_excess


class ExactConstraintInfeasible(MotifBalanceError):
    """Complete enumeration proved that no sequence satisfies the hard constraints."""

    code = "exact_constraint_infeasible"

    def __init__(self, *, sequence_space_size: int) -> None:
        super().__init__(
            f"Complete enumeration of all {sequence_space_size} sequences found no sequence "
            "that satisfies every hard avoidance ceiling. No portfolio was published.",
            field="avoiders",
            hint="Revise the avoider ceilings or the design length.",
        )
        self.sequence_space_size = sequence_space_size
        self.feasible_count = 0


class PortfolioInfeasible(MotifBalanceError):
    """The complete evaluated candidate pool has no feasible requested subset."""

    code = "portfolio_infeasible"

    def __init__(
        self,
        *,
        requested_count: int,
        valid_count: int,
        candidate_pool_size: int,
        minimum_distance: float | None,
        evaluations_used: int,
        best_score: float | None,
        design_space_exhausted: bool = False,
    ) -> None:
        scope = (
            "complete DNA design space" if design_space_exhausted else "evaluated candidate pool"
        )
        distance = (
            f" at minimum distance {minimum_distance:.17g}" if minimum_distance is not None else ""
        )
        message = (
            f"The {scope} contains no {requested_count}-candidate portfolio{distance}; "
            f"the largest admissible set found contains {valid_count}. No portfolio was published."
        )
        if not design_space_exhausted:
            message += " This does not establish infeasibility in the complete DNA design space."
        super().__init__(
            message,
            field="min_distance",
            hint="Increase evaluations, reduce count, or relax min_distance.",
        )
        self.requested_count = requested_count
        self.valid_count = valid_count
        self.candidate_pool_size = candidate_pool_size
        self.minimum_distance = minimum_distance
        self.evaluations_used = evaluations_used
        self.best_score = best_score
        self.design_space_exhausted = design_space_exhausted


class SelectionLimitReached(MotifBalanceError):
    """The bounded distance-selection traversal ended before resolving feasibility."""

    code = "selection_limit_reached"

    def __init__(
        self,
        *,
        nodes_explored: int,
        node_limit: int,
        candidate_pool_size: int,
        requested_count: int,
        minimum_distance: float,
    ) -> None:
        message = (
            f"Distance-constrained selection reached its {node_limit}-node limit after "
            f"exploring {nodes_explored} nodes in a pool of {candidate_pool_size} candidates. "
            "No portfolio was published. This does not establish that no feasible portfolio "
            "exists."
        )
        super().__init__(
            message,
            field="min_distance",
            hint="Increase the selection limit in a reviewed release, reduce count, or relax "
            "min_distance.",
        )
        self.nodes_explored = nodes_explored
        self.node_limit = node_limit
        self.candidate_pool_size = candidate_pool_size
        self.requested_count = requested_count
        self.minimum_distance = minimum_distance


class ArtifactError(MotifBalanceError):
    code = "artifact_error"
