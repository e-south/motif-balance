from __future__ import annotations

import pytest
from pydantic import ValidationError

from motif_balance import DesignSpec, MotifModel
from motif_balance.compile import compile_design, sequence_space_at_most
from motif_balance.constants import (
    MAX_CANDIDATE_COUNT,
    MAX_EVALUATIONS,
    MAX_SEQUENCE_LENGTH,
)
from motif_balance.errors import IncompatibleDesign
from motif_balance.model import MotifConversion


def test_public_models_are_strict_and_frozen(motif_a: MotifModel) -> None:
    with pytest.raises(ValidationError):
        MotifModel(
            motif_id="x",
            probabilities=((0.25, 0.25, 0.25, 0.25),),
            background=(0.25, 0.25, 0.25, 0.25),
            invented=True,
        )

    with pytest.raises(ValidationError):
        motif_a.motif_id = "changed"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("length", True),
        ("count", True),
        ("evaluations", True),
        ("seed", True),
        ("min_distance", False),
    ],
)
def test_design_rejects_boolean_numeric_values(
    motif_a: MotifModel,
    field: str,
    value: bool,
) -> None:
    payload = {
        "motifs": (motif_a,),
        "length": 2,
        "count": 1,
        "strands": "forward",
        "evaluations": 4,
        "seed": 3,
    }
    payload[field] = value

    with pytest.raises(ValidationError, match="boolean values are not valid"):
        DesignSpec(**payload)


def test_nested_scientific_models_reject_boolean_numeric_values() -> None:
    with pytest.raises(ValidationError, match="boolean values are not valid"):
        MotifModel(
            motif_id="invalid",
            probabilities=((True, 0.1, 0.1, 0.1),),
            background=(0.25, 0.25, 0.25, 0.25),
        )
    with pytest.raises(ValidationError, match="boolean values are not valid"):
        MotifConversion(method="jaspar_counts_to_probabilities_v1", prior_weight=True)


@pytest.mark.parametrize(
    "probabilities",
    [
        ((0.7, 0.1, 0.1),),
        ((0.7, 0.1, 0.1, 0.2),),
        ((0.7, 0.1, 0.2, 0.0),),
    ],
)
def test_motif_rejects_malformed_or_undefined_probabilities(
    probabilities: tuple[tuple[float, ...], ...],
) -> None:
    with pytest.raises(ValidationError):
        MotifModel(
            motif_id="invalid",
            probabilities=probabilities,
            background=(0.25, 0.25, 0.25, 0.25),
        )


def test_design_canonicalizes_mapping_and_rejects_key_identity_drift(motif_a: MotifModel) -> None:
    spec = DesignSpec(
        motifs={"motif_a": motif_a},
        length=2,
        count=1,
        strands="forward",
        evaluations=4,
        seed=3,
    )
    assert spec.motifs == (motif_a,)

    with pytest.raises(ValidationError, match="motif key"):
        DesignSpec(
            motifs={"different": motif_a},
            length=2,
            count=1,
            strands="forward",
            evaluations=4,
            seed=3,
        )


def test_compile_rejects_motif_wider_than_design(motif_a: MotifModel) -> None:
    spec = DesignSpec(
        motifs=(motif_a,),
        length=1,
        count=1,
        strands="forward",
        evaluations=4,
        seed=3,
    )
    with pytest.raises(IncompatibleDesign, match="wider"):
        compile_design(spec)


def test_compile_rejects_uninformative_motif() -> None:
    motif = MotifModel(
        motif_id="uniform",
        probabilities=((0.25, 0.25, 0.25, 0.25),),
        background=(0.25, 0.25, 0.25, 0.25),
    )
    spec = DesignSpec(
        motifs=(motif,),
        length=1,
        count=1,
        strands="forward",
        evaluations=4,
        seed=3,
    )
    with pytest.raises(IncompatibleDesign, match="normalization denominator"):
        compile_design(spec)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("length", MAX_SEQUENCE_LENGTH + 1),
        ("count", MAX_CANDIDATE_COUNT + 1),
        ("evaluations", MAX_EVALUATIONS + 1),
        ("length", 10**100),
    ],
)
def test_design_rejects_values_above_public_resource_limits(
    motif_a: MotifModel,
    field: str,
    value: int,
) -> None:
    payload = {
        "motifs": (motif_a,),
        "length": 2,
        "count": 1,
        "strands": "forward",
        "evaluations": 4,
        "seed": 3,
    }
    payload[field] = value
    if field == "count":
        payload["evaluations"] = value

    with pytest.raises(ValidationError):
        DesignSpec(**payload)


def test_design_rejects_portfolios_above_public_base_limit(motif_a: MotifModel) -> None:
    with pytest.raises(ValidationError, match="portfolio-base limit"):
        DesignSpec(
            motifs=(motif_a,),
            length=10_000,
            count=1_001,
            strands="forward",
            evaluations=1_001,
            seed=3,
        )


def test_design_rejects_match_tables_above_public_row_limit(motif_a: MotifModel) -> None:
    motifs = tuple(motif_a.model_copy(update={"motif_id": f"motif_{index}"}) for index in range(11))

    with pytest.raises(ValidationError, match="match-row limit"):
        DesignSpec(
            motifs=motifs,
            length=2,
            count=100_000,
            strands="forward",
            evaluations=100_000,
            seed=3,
        )


def test_design_rejects_pathological_scoring_work(motif_a: MotifModel) -> None:
    with pytest.raises(ValidationError, match="score-operation limit"):
        DesignSpec(
            motifs=(motif_a,),
            length=10_000,
            count=1,
            strands="both",
            evaluations=100_000,
            seed=3,
        )


def test_design_rejects_pathological_evaluated_bases(motif_a: MotifModel) -> None:
    with pytest.raises(ValidationError, match="evaluated-base limit"):
        DesignSpec(
            motifs=(motif_a,),
            length=300,
            count=1,
            strands="forward",
            evaluations=100_000,
            seed=3,
        )


def test_design_rejects_pathological_distance_validation(motif_a: MotifModel) -> None:
    with pytest.raises(ValidationError, match="distance-comparison limit"):
        DesignSpec(
            motifs=(motif_a,),
            length=100,
            count=20_000,
            strands="forward",
            evaluations=20_000,
            seed=3,
            min_distance=0.1,
        )


def test_sequence_space_is_computed_only_within_a_trusted_bound() -> None:
    assert sequence_space_at_most(4, 256) == 256
    assert sequence_space_at_most(4, 255) is None
    assert sequence_space_at_most(10_000, 1_000_000) is None
