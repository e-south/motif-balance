"""Source conversion receipts and positive motif probability contracts."""

from __future__ import annotations

import math
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from motif_balance.constants import (
    DNA_ALPHABET,
    LEGACY_SCORING_SEMANTICS,
    SCORING_SEMANTICS,
)

from .base import FrozenModel, _sha256


class MotifConversion(FrozenModel):
    schema_version: Literal["motif-conversion/v1", "motif-conversion/v2"] = "motif-conversion/v1"
    method: Literal[
        "jaspar_counts_to_probabilities_v1",
        "count_matrix_sqrt_n_background_prior_v1",
        "probability_matrix_prior_mixture_v1",
        "probability_matrix_target_background_v1",
    ]
    prior_weight: Annotated[float, Field(strict=True, ge=0.0, allow_inf_nan=False)] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_motif_id: str | None = None
    position_observed_counts: (
        tuple[Annotated[float, Field(strict=True, gt=0.0, allow_inf_nan=False)], ...] | None
    ) = Field(default=None, exclude_if=lambda value: value is None)
    position_prior_masses: (
        tuple[Annotated[float, Field(strict=True, gt=0.0, allow_inf_nan=False)], ...] | None
    ) = Field(default=None, exclude_if=lambda value: value is None)
    position_denominators: (
        tuple[Annotated[float, Field(strict=True, gt=0.0, allow_inf_nan=False)], ...] | None
    ) = Field(default=None, exclude_if=lambda value: value is None)
    source_background: (
        tuple[
            Annotated[float, Field(strict=True, gt=0.0, allow_inf_nan=False)],
            Annotated[float, Field(strict=True, gt=0.0, allow_inf_nan=False)],
            Annotated[float, Field(strict=True, gt=0.0, allow_inf_nan=False)],
            Annotated[float, Field(strict=True, gt=0.0, allow_inf_nan=False)],
        ]
        | None
    ) = Field(default=None, exclude_if=lambda value: value is None)
    target_background: (
        tuple[
            Annotated[float, Field(strict=True, gt=0.0, allow_inf_nan=False)],
            Annotated[float, Field(strict=True, gt=0.0, allow_inf_nan=False)],
            Annotated[float, Field(strict=True, gt=0.0, allow_inf_nan=False)],
            Annotated[float, Field(strict=True, gt=0.0, allow_inf_nan=False)],
        ]
        | None
    ) = Field(default=None, exclude_if=lambda value: value is None)
    target_background_policy: Literal["explicit_target_background_v1"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def validate_conversion_contract(self) -> Self:
        count_fields = (
            self.position_observed_counts,
            self.position_prior_masses,
            self.position_denominators,
        )
        background_fields = (
            self.source_background,
            self.target_background,
            self.target_background_policy,
        )
        if self.method == "count_matrix_sqrt_n_background_prior_v1":
            if self.schema_version != "motif-conversion/v2":
                raise ValueError("count-matrix conversion requires motif-conversion/v2")
            if self.prior_weight is not None or not self.source_motif_id:
                raise ValueError(
                    "count-matrix conversion requires a source_motif_id and no prior_weight"
                )
            if any(value is None for value in count_fields):
                raise ValueError("count-matrix conversion requires complete count metadata")
            if any(value is not None for value in background_fields):
                raise ValueError(
                    "target-background metadata is only valid for its probability-matrix conversion"
                )
            assert self.position_observed_counts is not None
            assert self.position_prior_masses is not None
            assert self.position_denominators is not None
            if not self.position_observed_counts or not (
                len(self.position_observed_counts)
                == len(self.position_prior_masses)
                == len(self.position_denominators)
            ):
                raise ValueError("count-matrix conversion requires aligned position metadata")
            for observed, prior, denominator in zip(
                self.position_observed_counts,
                self.position_prior_masses,
                self.position_denominators,
                strict=True,
            ):
                expected_prior = math.sqrt(observed)
                if abs(prior - expected_prior) > math.ulp(expected_prior):
                    raise ValueError("count-matrix position prior must equal sqrt(observed count)")
                expected_denominator = observed + prior
                if abs(denominator - expected_denominator) > math.ulp(expected_denominator):
                    raise ValueError(
                        "count-matrix position denominator must equal observed count plus prior"
                    )
            return self
        if self.method == "probability_matrix_target_background_v1":
            if self.schema_version != "motif-conversion/v2":
                raise ValueError("target-background conversion requires motif-conversion/v2")
            if any(value is not None for value in count_fields):
                raise ValueError("count metadata is only valid for the count-matrix conversion")
            if (
                self.prior_weight is None
                or not self.source_motif_id
                or any(value is None for value in background_fields)
            ):
                raise ValueError(
                    "target-background conversion requires a prior weight, source motif ID, "
                    "source background, target background, and policy"
                )
            if self.prior_weight <= 0.0:
                raise ValueError("target-background conversion requires a positive prior weight")
            assert self.source_background is not None
            assert self.target_background is not None
            if not math.isclose(sum(self.source_background), 1.0, abs_tol=1.0e-6):
                raise ValueError("source background must sum to one")
            if not math.isclose(sum(self.target_background), 1.0, abs_tol=1.0e-6):
                raise ValueError("target background must sum to one")
            return self
        if self.schema_version != "motif-conversion/v1":
            raise ValueError("motif-conversion/v2 does not admit the declared conversion method")
        if any(value is not None for value in count_fields):
            raise ValueError("count metadata is only valid for the count-matrix conversion")
        if any(value is not None for value in background_fields):
            raise ValueError(
                "target-background metadata is only valid for its probability-matrix conversion"
            )
        if self.prior_weight is None:
            raise ValueError("prior_weight is required for the declared conversion")
        if self.method == "probability_matrix_prior_mixture_v1" and (
            self.prior_weight <= 0.0 or not self.source_motif_id
        ):
            raise ValueError(
                "probability-matrix conversion requires a positive prior_weight and source_motif_id"
            )
        return self


class MotifModel(FrozenModel):
    schema_version: Literal["motif-model/v1", "motif-model/v2"] = "motif-model/v2"
    motif_id: str = Field(min_length=1, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    alphabet: tuple[Literal["A", "C", "G", "T"], ...] = DNA_ALPHABET
    probabilities: tuple[
        tuple[
            Annotated[float, Field(strict=True)],
            Annotated[float, Field(strict=True)],
            Annotated[float, Field(strict=True)],
            Annotated[float, Field(strict=True)],
        ],
        ...,
    ]
    background: tuple[
        Annotated[float, Field(strict=True)],
        Annotated[float, Field(strict=True)],
        Annotated[float, Field(strict=True)],
        Annotated[float, Field(strict=True)],
    ]
    source_digest: str | None = None
    source_name: str | None = None
    canonical_file_digest: str | None = None
    canonical_file_name: str | None = None
    conversion: MotifConversion | None = None

    @field_validator("alphabet")
    @classmethod
    def validate_alphabet(
        cls, value: tuple[Literal["A", "C", "G", "T"], ...]
    ) -> tuple[Literal["A", "C", "G", "T"], ...]:
        if value != DNA_ALPHABET:
            raise ValueError("alphabet must be exactly A, C, G, T")
        return value

    @field_validator("probabilities")
    @classmethod
    def validate_probabilities(
        cls, value: tuple[tuple[float, float, float, float], ...]
    ) -> tuple[tuple[float, float, float, float], ...]:
        if not value:
            raise ValueError("probabilities must contain at least one position")
        for index, row in enumerate(value):
            if any(not math.isfinite(entry) or entry <= 0.0 for entry in row):
                raise ValueError(
                    f"probability row {index} must contain four finite, positive values"
                )
            if not math.isclose(sum(row), 1.0, abs_tol=1.0e-6):
                raise ValueError(f"probability row {index} must sum to one")
        return value

    @field_validator("background")
    @classmethod
    def validate_background(
        cls, value: tuple[float, float, float, float]
    ) -> tuple[float, float, float, float]:
        if any(not math.isfinite(entry) or entry <= 0.0 for entry in value):
            raise ValueError("background must contain four finite, positive values")
        if not math.isclose(sum(value), 1.0, abs_tol=1.0e-6):
            raise ValueError("background must sum to one")
        return value

    @field_validator("source_digest", "canonical_file_digest")
    @classmethod
    def validate_source_digest(cls, value: str | None) -> str | None:
        if value is not None and (
            len(value) != 64 or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError("source digests must be lowercase SHA-256 digests")
        return value

    @field_validator("source_name", "canonical_file_name")
    @classmethod
    def validate_source_name(cls, value: str | None) -> str | None:
        if value is not None and (
            not value or value in {".", ".."} or "/" in value or "\\" in value
        ):
            raise ValueError("source names must be basenames, not paths")
        return value

    @model_validator(mode="after")
    def validate_conversion_width(self) -> Self:
        if (
            self.conversion is not None
            and self.conversion.method == "count_matrix_sqrt_n_background_prior_v1"
            and self.schema_version != "motif-model/v2"
        ):
            raise ValueError("count-matrix sqrt-N conversion requires motif-model/v2")
        if (
            self.conversion is not None
            and self.conversion.method == "probability_matrix_target_background_v1"
            and self.schema_version != "motif-model/v2"
        ):
            raise ValueError("target-background conversion requires motif-model/v2")
        if (
            self.conversion is not None
            and self.conversion.method == "count_matrix_sqrt_n_background_prior_v1"
            and self.conversion.position_observed_counts is not None
            and len(self.conversion.position_observed_counts) != self.width
        ):
            raise ValueError("count-matrix conversion position metadata must equal motif width")
        if (
            self.conversion is not None
            and self.conversion.method == "probability_matrix_target_background_v1"
            and self.conversion.target_background != self.background
        ):
            raise ValueError("conversion target background must equal model background")
        return self

    @property
    def width(self) -> int:
        return len(self.probabilities)

    @property
    def model_digest(self) -> str:
        scoring_semantics = (
            LEGACY_SCORING_SEMANTICS
            if self.schema_version == "motif-model/v1"
            else SCORING_SEMANTICS
        )
        return _sha256(
            {
                "schema_version": self.schema_version,
                "alphabet": self.alphabet,
                "probabilities": self.probabilities,
                "background": self.background,
                "scoring_semantics": scoring_semantics,
            }
        )
