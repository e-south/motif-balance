"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/model/variants.py

Immutable, explicitly enumerated sequence libraries around one selected design.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from itertools import product
from math import prod
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .base import FrozenModel
from .design import DesignSpec
from .evaluation import Evaluation

IUPAC = dict(
    zip(
        (
            "A",
            "C",
            "G",
            "T",
            "AC",
            "AG",
            "AT",
            "CG",
            "CT",
            "GT",
            "ACG",
            "ACT",
            "AGT",
            "CGT",
            "ACGT",
        ),
        ("A", "C", "G", "T", "M", "R", "W", "S", "Y", "K", "V", "H", "D", "B", "N"),
        strict=True,
    )
)
Finite = Annotated[float, Field(strict=True, allow_inf_nan=False)]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]


class Substitution(FrozenModel):
    """One parental single substitution, including the resulting complete rescan."""

    position: Annotated[int, Field(strict=True, ge=0)]
    parent_base: Literal["A", "C", "G", "T"]
    base: Literal["A", "C", "G", "T"]
    evaluation: Evaluation
    component_changes: tuple[Finite, ...]
    changed_desired_sites: tuple[str, ...]
    status: Literal["passes_alone", "site_changed", "score_loss"]


class VariantVerification(FrozenModel):
    encoded_sequence_count: PositiveInt
    maximum_component_loss: Annotated[float, Field(strict=True, ge=0.0, allow_inf_nan=False)]
    minimum_balance: Annotated[float, Field(strict=True, ge=0.0, allow_inf_nan=False)]
    desired_sites: Literal["preserved"] = "preserved"
    outcome: Literal["parent_only", "diversified"]


class VariantLibrary(FrozenModel):
    schema_version: Literal["variant-library/v1"] = "variant-library/v1"
    algorithm: Literal["greedy_product_checked_v1"] = "greedy_product_checked_v1"
    package_version: str
    runtime_contract: str
    build_lock_sha256: str
    problem_id: str
    spec: DesignSpec
    parent: Evaluation
    max_score_loss: Annotated[float, Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False)]
    max_variants: Annotated[int, Field(strict=True, ge=1, le=256)]
    editable_positions: tuple[Annotated[int, Field(strict=True, ge=0)], ...]
    allowed_bases: tuple[str, ...]
    template: str
    variants: tuple[Evaluation, ...]
    substitutions: tuple[Substitution, ...]
    verification: VariantVerification
    evaluations_used: PositiveInt
    score_operations: PositiveInt
    size_rejected_expansions: Annotated[int, Field(strict=True, ge=0)]
    score_rejected_expansions: Annotated[int, Field(strict=True, ge=0)]
    stop_reason: Literal["size_cap", "no_further_passing_expansion"]

    @model_validator(mode="after")
    def validate_library(self) -> Self:
        length = len(self.parent.sequence)
        if length != self.spec.length or len(self.allowed_bases) != length:
            raise ValueError("library length must match parent and specification")
        if self.editable_positions != tuple(sorted(set(self.editable_positions))) or any(
            p >= length for p in self.editable_positions
        ):
            raise ValueError("editable positions must be unique, ordered, and within the parent")
        for i, bases in enumerate(self.allowed_bases):
            if bases not in IUPAC or self.parent.sequence[i] not in bases:
                raise ValueError(
                    "allowed bases must be ordered distinct DNA bases including parent"
                )
            if i not in self.editable_positions and bases != self.parent.sequence[i]:
                raise ValueError("library changes an uneditable position")
        count = prod(map(len, self.allowed_bases))
        if count > self.max_variants or count != len(self.variants):
            raise ValueError("every encoded sequence must be included within the library cap")
        if self.template != "".join(IUPAC[b] for b in self.allowed_bases):
            raise ValueError("template must encode exactly the allowed bases")
        expected = {"".join(bases) for bases in product(*self.allowed_bases)}
        if expected != {v.sequence for v in self.variants} or self.variants[0] != self.parent:
            raise ValueError("variants must enumerate the product exactly, with parent first")
        for variant in self.variants:
            if len(variant.matches) != len(self.parent.matches):
                raise ValueError("every variant must include every parental model")
            for parent, match in zip(self.parent.matches, variant.matches, strict=True):
                if (parent.motif_id, parent.spec_direction) != (
                    match.motif_id,
                    match.spec_direction,
                ):
                    raise ValueError("variant match identities must equal parental identities")
                if parent.spec_satisfaction - match.spec_satisfaction > self.max_score_loss + 1e-12:
                    raise ValueError("variant exceeds a component score-loss limit")
                if parent.spec_direction == "seek" and (
                    parent.start,
                    parent.end,
                    parent.strand,
                ) != (match.start, match.end, match.strand):
                    raise ValueError("variant changes a desired selected site")
        expected_summary = VariantVerification(
            encoded_sequence_count=self.encoded_sequence_count,
            maximum_component_loss=self.maximum_component_loss,
            minimum_balance=self.minimum_balance,
            outcome=self.status,
        )
        if self.verification != expected_summary:
            raise ValueError("verification summary must agree with the enumerated variants")
        return self

    @property
    def encoded_sequence_count(self) -> int:
        return len(self.variants)

    @property
    def status(self) -> Literal["parent_only", "diversified"]:
        return "parent_only" if len(self.variants) == 1 else "diversified"

    @property
    def maximum_component_loss(self) -> float:
        return max(
            0.0,
            *(
                p.spec_satisfaction - m.spec_satisfaction
                for v in self.variants
                for p, m in zip(self.parent.matches, v.matches, strict=True)
            ),
        )

    @property
    def minimum_balance(self) -> float:
        return min(v.balance_score for v in self.variants)
