from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from motif_balance.constants import (
    DNA_ALPHABET,
    OBJECTIVE_SEMANTICS,
    SCORING_SEMANTICS,
    TIE_BREAK_SEMANTICS,
)


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class MotifModel(FrozenModel):
    schema_version: Literal["motif-model/v1"] = "motif-model/v1"
    motif_id: str = Field(min_length=1, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    alphabet: tuple[Literal["A", "C", "G", "T"], ...] = DNA_ALPHABET
    probabilities: tuple[tuple[float, float, float, float], ...]
    background: tuple[float, float, float, float]
    source_digest: str | None = None
    source_name: str | None = None

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

    @field_validator("source_digest")
    @classmethod
    def validate_source_digest(cls, value: str | None) -> str | None:
        if value is not None and (
            len(value) != 64 or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError("source_digest must be a lowercase SHA-256 digest")
        return value

    @field_validator("source_name")
    @classmethod
    def validate_source_name(cls, value: str | None) -> str | None:
        if value is not None and (
            not value or value in {".", ".."} or "/" in value or "\\" in value
        ):
            raise ValueError("source_name must be a basename, not a path")
        return value

    @property
    def width(self) -> int:
        return len(self.probabilities)

    @property
    def model_digest(self) -> str:
        return _sha256(
            {
                "schema_version": self.schema_version,
                "alphabet": self.alphabet,
                "probabilities": self.probabilities,
                "background": self.background,
                "scoring_semantics": SCORING_SEMANTICS,
            }
        )


class DesignSpec(FrozenModel):
    schema_version: Literal["design-spec/v1"] = "design-spec/v1"
    motifs: tuple[MotifModel, ...]
    length: Annotated[int, Field(gt=0)]
    count: Annotated[int, Field(gt=0)]
    strands: Literal["forward", "both"] = "both"
    evaluations: Annotated[int, Field(gt=0)]
    seed: Annotated[int, Field(ge=0)]
    min_distance: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    scoring_semantics: Literal["normalized_llr_v1"] = SCORING_SEMANTICS
    objective_semantics: Literal["weakest_score_v1"] = OBJECTIVE_SEMANTICS
    tie_break_semantics: Literal["leftmost_plus_first_v1"] = TIE_BREAK_SEMANTICS

    @model_validator(mode="before")
    @classmethod
    def canonicalize_motif_mapping(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        result = dict(value)
        motifs = result.get("motifs")
        if isinstance(motifs, Mapping):
            canonical: list[object] = []
            for key in sorted(motifs):
                if not isinstance(key, str):
                    raise ValueError("motif keys must be strings")
                motif = motifs[key]
                motif_id: str | None
                if isinstance(motif, MotifModel):
                    motif_id = motif.motif_id
                elif isinstance(motif, Mapping):
                    raw_motif_id = motif.get("motif_id")
                    motif_id = raw_motif_id if isinstance(raw_motif_id, str) else None
                else:
                    motif_id = None
                if motif_id != key:
                    raise ValueError(
                        f"motif key '{key}' does not match model motif_id '{motif_id}'"
                    )
                canonical.append(motif)
            result["motifs"] = tuple(canonical)
        return result

    @field_validator("motifs")
    @classmethod
    def validate_motifs(cls, value: tuple[MotifModel, ...]) -> tuple[MotifModel, ...]:
        if not value:
            raise ValueError("motifs must contain at least one model")
        ordered = tuple(sorted(value, key=lambda motif: motif.motif_id))
        ids = [motif.motif_id for motif in ordered]
        if len(ids) != len(set(ids)):
            raise ValueError("motif identifiers must be unique")
        return ordered

    @model_validator(mode="after")
    def validate_budget(self) -> Self:
        if self.count > self.evaluations:
            raise ValueError("evaluations must be at least count")
        return self


class MotifMatch(FrozenModel):
    motif_id: str
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    strand: Literal["+", "-"]
    matched_sequence: str
    raw_score: float
    normalized_score: Annotated[float, Field(ge=0.0)]

    @model_validator(mode="after")
    def validate_coordinates(self) -> Self:
        if self.end <= self.start:
            raise ValueError("match end must be greater than start")
        if self.end - self.start != len(self.matched_sequence):
            raise ValueError("match coordinates must equal matched-sequence width")
        if set(self.matched_sequence) - set(DNA_ALPHABET):
            raise ValueError("matched_sequence must contain only A, C, G, and T")
        if not math.isfinite(self.raw_score) or not math.isfinite(self.normalized_score):
            raise ValueError("match scores must be finite")
        return self


class Evaluation(FrozenModel):
    sequence: str
    balance_score: Annotated[float, Field(ge=0.0)]
    matches: tuple[MotifMatch, ...]

    @model_validator(mode="after")
    def validate_balance(self) -> Self:
        if set(self.sequence) - set(DNA_ALPHABET):
            raise ValueError("sequence must contain only A, C, G, and T")
        if not self.matches:
            raise ValueError("evaluation must contain at least one motif match")
        weakest = min(match.normalized_score for match in self.matches)
        if not math.isclose(self.balance_score, weakest, abs_tol=1.0e-12):
            raise ValueError("balance_score must equal the weakest normalized motif score")
        return self


class Candidate(FrozenModel):
    candidate_id: str = Field(pattern=r"^candidate-[0-9a-f]{16}$")
    rank: Annotated[int, Field(gt=0)]
    sequence: str
    balance_score: Annotated[float, Field(ge=0.0)]
    matches: tuple[MotifMatch, ...]

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        Evaluation(
            sequence=self.sequence,
            balance_score=self.balance_score,
            matches=self.matches,
        )
        return self


class ArtifactDigest(FrozenModel):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: Annotated[int, Field(ge=0)]


class RunManifest(FrozenModel):
    schema_version: Literal["run-manifest/v1"] = "run-manifest/v1"
    package_version: str
    runtime_contract: str
    build_lock_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    problem_id: str = Field(pattern=r"^problem-[0-9a-f]{24}$")
    run_id: str = Field(pattern=r"^run-[0-9a-f]{24}$")
    bundle_id: str = Field(pattern=r"^bundle-[0-9a-f]{24}$")
    search_engine: str
    search_engine_version: str
    rng: str
    evaluation_count: Annotated[int, Field(gt=0)]
    unique_evaluations: Annotated[int, Field(gt=0)]
    completion_status: Literal["exhaustive", "budget_exhausted"]
    optimizer_parity_status: Literal["not_applicable", "not_established"]
    artifacts: tuple[ArtifactDigest, ...]

    @model_validator(mode="after")
    def validate_evaluation_counts(self) -> Self:
        if self.unique_evaluations > self.evaluation_count:
            raise ValueError("unique_evaluations cannot exceed evaluation_count")
        return self


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
        if self.problem_id != self.manifest.problem_id or self.run_id != self.manifest.run_id:
            raise ValueError("portfolio and manifest identities must agree")
        if len(self.candidates) != self.spec.count:
            raise ValueError("portfolio must contain exactly spec.count candidates")
        expected_ids = {motif.motif_id for motif in self.spec.motifs}
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
            if candidate.sequence in seen_sequences:
                raise ValueError("candidate sequences must be unique")
            seen_sequences.add(candidate.sequence)
            key = (-candidate.balance_score, candidate.sequence)
            if previous_key is not None and key < previous_key:
                raise ValueError("candidates must be sorted by score then sequence")
            previous_key = key
            for match in candidate.matches:
                if match.end > self.spec.length:
                    raise ValueError("match coordinates exceed candidate sequence")
        if self.spec.min_distance is not None:
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
    def matches(self) -> tuple[MotifMatch, ...]:
        return tuple(match for candidate in self.candidates for match in candidate.matches)
