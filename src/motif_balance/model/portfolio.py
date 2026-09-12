"""Cross-record portfolio invariants and unchanged selection boundaries."""

from __future__ import annotations

from typing import Self

from pydantic import model_validator

from motif_balance.constants import (
    DIRECTIONAL_OBJECTIVE_SEMANTICS,
    LEGACY_SCORING_SEMANTICS,
    SCORING_SEMANTICS,
)

from .base import FrozenModel
from .design import DesignSpec
from .evaluation import Candidate, Evaluation, MotifMatch
from .manifest import RunManifest


def _normalized_hamming_distance(left: str, right: str) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("portfolio candidates must have equal, nonzero lengths")
    return sum(a != b for a, b in zip(left, right, strict=True)) / len(left)


class PortfolioRecord(FrozenModel):
    problem_id: str
    run_id: str
    spec: DesignSpec
    candidates: tuple[Candidate, ...]
    manifest: RunManifest

    @model_validator(mode="after")
    def validate_portfolio(self) -> Self:
        current_contract = (
            self.manifest.schema_version == "run-manifest/v5"
            and self.spec.schema_version == "design-spec/v2"
        ) and self.spec.scoring_semantics == SCORING_SEMANTICS
        directional_contract = (
            self.manifest.schema_version == "run-manifest/v6"
            and self.spec.schema_version == "design-spec/v3"
            and self.spec.scoring_semantics == SCORING_SEMANTICS
            and self.spec.objective_semantics == DIRECTIONAL_OBJECTIVE_SEMANTICS
        )
        legacy_contract = (
            self.manifest.schema_version
            in {"run-manifest/v2", "run-manifest/v3", "run-manifest/v4"}
            and self.spec.schema_version == "design-spec/v1"
            and self.spec.scoring_semantics == LEGACY_SCORING_SEMANTICS
        )
        if not (current_contract or directional_contract or legacy_contract):
            raise ValueError("portfolio violates the manifest/design scoring version matrix")
        if self.problem_id != self.manifest.problem_id or self.run_id != self.manifest.run_id:
            raise ValueError("portfolio and manifest identities must agree")
        if len(self.candidates) != self.spec.count:
            raise ValueError("portfolio must contain exactly spec.count candidates")
        expected_ids = {motif.motif_id for motif in self.spec.scored_motifs}
        expected_avoider_ids = {item.motif.motif_id for item in self.spec.avoiders}
        best_observed = self.manifest.best_observed
        if best_observed is not None:
            if len(best_observed.sequence) != self.spec.length:
                raise ValueError("best observed sequence length must equal spec.length")
            if {match.motif_id for match in best_observed.matches} != expected_ids:
                raise ValueError(
                    "best observed evaluation must contain exactly one match per motif"
                )
            if len(best_observed.matches) != len(expected_ids):
                raise ValueError("best observed evaluation contains duplicate motif matches")
            if {
                match.motif_id for match in best_observed.avoidance_matches
            } != expected_avoider_ids or len(best_observed.avoidance_matches) != len(
                expected_avoider_ids
            ):
                raise ValueError(
                    "best observed evaluation must contain exactly one match per avoider"
                )
            if not best_observed.constraint_feasible:
                raise ValueError("best observed published evaluation must satisfy hard constraints")
        seen_candidate_ids: set[str] = set()
        seen_sequences: set[str] = set()
        previous_key: tuple[float, str] | None = None
        for expected_rank, candidate in enumerate(self.candidates, start=1):
            if candidate.rank != expected_rank:
                raise ValueError("candidate ranks must be consecutive from one")
            if len(candidate.sequence) != self.spec.length:
                raise ValueError("candidate sequence length must equal spec.length")
            if {match.motif_id for match in candidate.matches} != expected_ids:
                raise ValueError("candidate must contain exactly one match per motif")
            if len(candidate.matches) != len(expected_ids):
                raise ValueError("candidate contains duplicate motif matches")
            if {match.motif_id for match in candidate.avoidance_matches} != expected_avoider_ids:
                raise ValueError("candidate must contain exactly one match per avoider")
            if len(candidate.avoidance_matches) != len(expected_avoider_ids):
                raise ValueError("candidate contains duplicate avoider matches")
            if not candidate.constraint_feasible:
                raise ValueError("published candidate must satisfy hard constraints")
            if candidate.sequence in seen_sequences:
                raise ValueError("candidate sequences must be unique")
            if candidate.candidate_id in seen_candidate_ids:
                raise ValueError("candidate identifiers must be unique")
            seen_candidate_ids.add(candidate.candidate_id)
            seen_sequences.add(candidate.sequence)
            key = (-candidate.balance_score, candidate.sequence)
            if previous_key is not None and key < previous_key:
                raise ValueError("candidates must be sorted by score then sequence")
            previous_key = key
            for match in (*candidate.matches, *candidate.avoidance_matches):
                if match.end > self.spec.length:
                    raise ValueError("match coordinates exceed candidate sequence")
            if best_observed is not None:
                if candidate.balance_score > best_observed.balance_score + 1.0e-12:
                    raise ValueError(
                        "selected candidate score cannot exceed the best observed score"
                    )
                if candidate.sequence == best_observed.sequence and (
                    candidate.balance_score != best_observed.balance_score
                    or candidate.matches != best_observed.matches
                    or candidate.avoidance_matches != best_observed.avoidance_matches
                ):
                    raise ValueError("selected and best observed records disagree for one sequence")
        if self.spec.min_distance is not None and self.spec.min_distance > 0.0:
            for index, left in enumerate(self.candidates):
                for right in self.candidates[index + 1 :]:
                    if (
                        _normalized_hamming_distance(left.sequence, right.sequence) + 1.0e-12
                        < self.spec.min_distance
                    ):
                        raise ValueError("candidate pair violates min_distance")
        return self

    @property
    def best(self) -> Candidate:
        return self.candidates[0]

    @property
    def best_observed(self) -> Evaluation | None:
        return self.manifest.best_observed

    @property
    def matches(self) -> tuple[MotifMatch, ...]:
        return tuple(match for candidate in self.candidates for match in candidate.matches)

    @property
    def avoidance_matches(self) -> tuple[MotifMatch, ...]:
        return tuple(
            match for candidate in self.candidates for match in candidate.avoidance_matches
        )
