from __future__ import annotations

import pytest
from pydantic import ValidationError

from motif_balance import DesignSpec, MotifModel, design
from motif_balance.compile import compile_design, sequence_space_at_most
from motif_balance.constants import (
    MAX_CANDIDATE_COUNT,
    MAX_EVALUATIONS,
    MAX_SEQUENCE_LENGTH,
)
from motif_balance.errors import IncompatibleDesign
from motif_balance.model import MotifConversion, PortfolioRecord


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


def test_model_identity_preserves_v1_receipts_and_distinguishes_v2() -> None:
    payload = {
        "motif_id": "identity",
        "probabilities": ((0.7, 0.1, 0.1, 0.1),),
        "background": (0.25, 0.25, 0.25, 0.25),
    }
    legacy = MotifModel(schema_version="motif-model/v1", **payload)
    current = MotifModel(schema_version="motif-model/v2", **payload)

    assert legacy.model_digest == (
        "b18f59802cb2e905ce66b79b198f001a766f970fc5c2ec758a70ed3755093a05"
    )
    assert current.model_digest == (
        "0653221b1809dbded9e936d72f0dcef5cfefb466fdbda0d9e4a399539647f144"
    )
    assert legacy.model_digest != current.model_digest


def test_v1_design_is_read_only_and_cannot_publish_v5() -> None:
    motif = MotifModel(
        schema_version="motif-model/v1",
        motif_id="legacy",
        probabilities=((0.7, 0.1, 0.1, 0.1),),
        background=(0.25, 0.25, 0.25, 0.25),
    )
    spec = DesignSpec(
        schema_version="design-spec/v1",
        motifs=(motif,),
        length=1,
        count=1,
        strands="forward",
        evaluations=4,
        seed=1,
        scoring_semantics="normalized_llr_v1",
    )

    with pytest.raises(IncompatibleDesign, match="read-only"):
        design(spec)


def test_manifest_matrix_rejects_relabelled_current_portfolio(pairwise_spec: DesignSpec) -> None:
    payload = design(pairwise_spec).model_dump(mode="python")
    payload["manifest"]["schema_version"] = "run-manifest/v4"

    with pytest.raises(ValidationError, match="manifest/design scoring version matrix"):
        PortfolioRecord.model_validate(payload)


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


def test_probability_matrix_prior_mixture_is_explicit_and_validated() -> None:
    conversion = MotifConversion(
        method="probability_matrix_prior_mixture_v1",
        prior_weight=0.1,
        source_motif_id="source_cpxR",
    )
    motif = MotifModel(
        motif_id="cpxR",
        probabilities=((0.93, 0.02, 0.02, 0.03),),
        background=(0.3, 0.2, 0.2, 0.3),
        conversion=conversion,
    )

    assert motif.conversion == conversion
    assert motif.model_dump(mode="json")["conversion"] == {
        "schema_version": "motif-conversion/v1",
        "method": "probability_matrix_prior_mixture_v1",
        "prior_weight": 0.1,
        "source_motif_id": "source_cpxR",
    }


@pytest.mark.parametrize(
    ("prior_weight", "source_motif_id"),
    [(0.0, "source_cpxR"), (0.1, None), (0.1, "")],
)
def test_probability_matrix_prior_mixture_rejects_incomplete_provenance(
    prior_weight: float,
    source_motif_id: str | None,
) -> None:
    with pytest.raises(ValidationError, match="probability-matrix conversion"):
        MotifConversion(
            method="probability_matrix_prior_mixture_v1",
            prior_weight=prior_weight,
            source_motif_id=source_motif_id,
        )


@pytest.mark.parametrize("prior_weight", [float("nan"), float("inf")])
def test_motif_conversion_rejects_nonfinite_prior_weight(prior_weight: float) -> None:
    with pytest.raises(ValidationError, match="finite number"):
        MotifConversion(
            method="probability_matrix_prior_mixture_v1",
            prior_weight=prior_weight,
            source_motif_id="source_cpxR",
        )


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
