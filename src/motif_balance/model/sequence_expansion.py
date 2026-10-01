"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/model/sequence_expansion.py

Explicit sequence lists and compact, replayable expansion decisions.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from math import isclose
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .base import FrozenModel
from .design import DesignSpec
from .evaluation import Evaluation

Count = Annotated[int, Field(strict=True, ge=0)]
Score = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]


def sequence_code(sequence: str) -> int:
    """An exact two-bit identity for fixed-length concrete DNA, not a hash."""
    code = 0
    for base in sequence:
        code = (code << 2) | "ACGT".index(base)
    return code


class ExpansionTrial(FrozenModel):
    """One tested substitution, reconstructible without retaining another DNA copy."""

    source_index: Count
    position: Count
    base: Literal["A", "C", "G", "T"]
    balance_score: Score
    status: Literal["retained", "below_floor", "site_changed"]


class SequenceExpansion(FrozenModel):
    schema_version: Literal["sequence-expansion/v1"] = "sequence-expansion/v1"
    algorithm: Literal["qualifying_neighbours_bfs_v1"] = "qualifying_neighbours_bfs_v1"
    package_version: str
    runtime_contract: str
    build_lock_sha256: str
    spec: DesignSpec
    parent: Evaluation
    min_balance: Score
    max_variants: Annotated[int, Field(strict=True, ge=1, le=1024)]
    max_evaluations: Annotated[int, Field(strict=True, ge=1, le=100_000)]
    editable_positions: tuple[Count, ...]
    variants: tuple[Evaluation, ...]
    trials: tuple[ExpansionTrial, ...]
    score_operations: Annotated[int, Field(strict=True, ge=1)]
    stop_reason: Literal["variant_limit", "evaluation_limit", "frontier_exhausted"]

    @property
    def evaluations_used(self) -> int:
        return 1 + len(self.trials)

    @property
    def minimum_balance(self) -> float:
        return min(v.balance_score for v in self.variants)

    @model_validator(mode="after")
    def validate_expansion(self) -> Self:
        length = self.spec.length
        if not self.variants or self.variants[0] != self.parent:
            raise ValueError("the parent must be the first retained sequence")
        if self.editable_positions != tuple(sorted(set(self.editable_positions))) or any(
            p >= length for p in self.editable_positions
        ):
            raise ValueError("editable positions must be ordered, unique, and within the DNA")
        if len(self.variants) > self.max_variants or self.evaluations_used > self.max_evaluations:
            raise ValueError("expansion exceeds its declared limits")
        if self.stop_reason == "variant_limit" and len(self.variants) != self.max_variants:
            raise ValueError("variant limit was not reached")
        if self.stop_reason == "evaluation_limit" and self.evaluations_used != self.max_evaluations:
            raise ValueError("evaluation limit was not reached")
        identities = tuple((s.motif.motif_id, s.direction) for s in self.spec.specifications)
        for variant in self.variants:
            if (
                len(variant.sequence) != length
                or tuple((m.motif_id, m.spec_direction) for m in variant.matches) != identities
            ):
                raise ValueError("retained sequence and model identities must match the request")
            if variant.balance_score < self.min_balance - 1e-12:
                raise ValueError("a retained sequence fails the floor")
            if any(
                a != b and p not in self.editable_positions
                for p, (a, b) in enumerate(zip(self.parent.sequence, variant.sequence, strict=True))
            ):
                raise ValueError("a retained sequence changes an uneditable position")
            for parent, match in zip(self.parent.matches, variant.matches, strict=True):
                if parent.spec_direction == "seek" and (
                    parent.start,
                    parent.end,
                    parent.strand,
                ) != (match.start, match.end, match.strand):
                    raise ValueError("a retained sequence changes a selected desired site")
        seen = {sequence_code(self.parent.sequence)}
        retained_count = 1
        for trial in self.trials:
            if (
                trial.source_index >= retained_count
                or trial.position not in self.editable_positions
            ):
                raise ValueError(
                    "a trial must edit an already retained sequence at an editable position"
                )
            source = self.variants[trial.source_index].sequence
            if source[trial.position] == trial.base:
                raise ValueError("a trial must change a nucleotide")
            sequence = source[: trial.position] + trial.base + source[trial.position + 1 :]
            code = sequence_code(sequence)
            if code in seen:
                raise ValueError("a sequence may be tested only once")
            seen.add(code)
            if trial.status == "retained":
                if retained_count >= len(self.variants):
                    raise ValueError("a passing trial was lost from the returned list")
                variant = self.variants[retained_count]
                if variant.sequence != sequence or not isclose(
                    variant.balance_score, trial.balance_score, rel_tol=0, abs_tol=1e-12
                ):
                    raise ValueError("passing trials must match the returned list in order")
                retained_count += 1
            elif trial.status == "below_floor" and trial.balance_score >= self.min_balance - 1e-12:
                raise ValueError("a below-floor trial meets the floor")
        if retained_count != len(self.variants):
            raise ValueError("every retained variant requires a passing trial")
        return self
