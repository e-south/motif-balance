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


class IncompatibleDesign(MotifBalanceError):
    code = "incompatible_design"


class SearchExhausted(MotifBalanceError):
    code = "search_exhausted"

    def __init__(
        self,
        *,
        requested_count: int,
        valid_count: int,
        evaluations_used: int,
        best_score: float | None,
        limiting_condition: str,
        hint: str,
    ) -> None:
        message = (
            f"Requested {requested_count} candidates but found {valid_count} valid candidates "
            f"within {evaluations_used} evaluations ({limiting_condition})."
        )
        super().__init__(message, field="count", hint=hint)
        self.requested_count = requested_count
        self.valid_count = valid_count
        self.evaluations_used = evaluations_used
        self.best_score = best_score
        self.limiting_condition = limiting_condition


class ArtifactError(MotifBalanceError):
    code = "artifact_error"
