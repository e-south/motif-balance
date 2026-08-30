from __future__ import annotations

import math

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

    with pytest.raises(ValidationError, match="run-manifest/v4 requires search-diagnostics/v1"):
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


def test_count_matrix_sqrt_n_conversion_is_explicit_and_width_bound() -> None:
    conversion = MotifConversion(
        schema_version="motif-conversion/v2",
        method="count_matrix_sqrt_n_background_prior_v1",
        source_motif_id="MA0001.1",
        position_observed_counts=(4.0, 4.0),
        position_prior_masses=(2.0, 2.0),
        position_denominators=(6.0, 6.0),
    )
    motif = MotifModel(
        motif_id="count_derived",
        probabilities=((0.8, 0.05, 0.1, 0.05), (0.3, 0.2, 0.2, 0.3)),
        background=(0.4, 0.1, 0.2, 0.3),
        conversion=conversion,
    )

    assert motif.model_dump(mode="json", exclude_none=True)["conversion"] == {
        "schema_version": "motif-conversion/v2",
        "method": "count_matrix_sqrt_n_background_prior_v1",
        "source_motif_id": "MA0001.1",
        "position_observed_counts": [4.0, 4.0],
        "position_prior_masses": [2.0, 2.0],
        "position_denominators": [6.0, 6.0],
    }

    with pytest.raises(ValidationError, match="motif width"):
        MotifModel(
            motif_id="wrong_width",
            probabilities=((0.8, 0.05, 0.1, 0.05),),
            background=(0.4, 0.1, 0.2, 0.3),
            conversion=conversion,
        )

    with pytest.raises(ValidationError, match="requires motif-model/v2"):
        MotifModel(
            schema_version="motif-model/v1",
            motif_id="historical_semantics",
            probabilities=((0.8, 0.05, 0.1, 0.05), (0.3, 0.2, 0.2, 0.3)),
            background=(0.4, 0.1, 0.2, 0.3),
            conversion=conversion,
        )


def test_probability_matrix_target_background_conversion_is_explicit_and_model_bound() -> None:
    conversion = MotifConversion(
        schema_version="motif-conversion/v2",
        method="probability_matrix_target_background_v1",
        prior_weight=0.1,
        source_motif_id="source_model",
        source_background=(0.4, 0.1, 0.2, 0.3),
        target_background=(0.25, 0.25, 0.25, 0.25),
        target_background_policy="explicit_target_background_v1",
    )
    motif = MotifModel(
        motif_id="target_background",
        probabilities=((1.025 / 1.1, 0.025 / 1.1, 0.025 / 1.1, 0.025 / 1.1),),
        background=(0.25, 0.25, 0.25, 0.25),
        conversion=conversion,
    )

    assert motif.model_dump(mode="json", exclude_none=True)["conversion"] == {
        "schema_version": "motif-conversion/v2",
        "method": "probability_matrix_target_background_v1",
        "prior_weight": 0.1,
        "source_motif_id": "source_model",
        "source_background": [0.4, 0.1, 0.2, 0.3],
        "target_background": [0.25, 0.25, 0.25, 0.25],
        "target_background_policy": "explicit_target_background_v1",
    }
    without_provenance = MotifModel(
        motif_id="other_name",
        probabilities=motif.probabilities,
        background=motif.background,
    )
    assert motif.model_digest == without_provenance.model_digest

    with pytest.raises(ValidationError, match="requires motif-model/v2"):
        MotifModel(
            schema_version="motif-model/v1",
            motif_id="historical_semantics",
            probabilities=motif.probabilities,
            background=motif.background,
            conversion=conversion,
        )


@pytest.mark.parametrize(
    "conversion",
    [
        {
            "schema_version": "motif-conversion/v2",
            "method": "probability_matrix_target_background_v1",
            "prior_weight": 0.1,
            "source_motif_id": "source_model",
            "source_background": (0.4, 0.1, 0.2, 0.3),
            "target_background": (0.25, 0.25, 0.25, 0.25),
            "target_background_policy": "invented_policy",
        },
        {
            "schema_version": "motif-conversion/v2",
            "method": "probability_matrix_target_background_v1",
            "prior_weight": 0.1,
            "source_motif_id": "source_model",
            "source_background": (0.4, 0.1, 0.2),
            "target_background": (0.25, 0.25, 0.25, 0.25),
            "target_background_policy": "explicit_target_background_v1",
        },
        {
            "schema_version": "motif-conversion/v2",
            "method": "probability_matrix_target_background_v1",
            "prior_weight": 0.1,
            "source_motif_id": "source_model",
            "source_background": (0.4, 0.1, 0.2, 0.3),
            "target_background": (0.25, 0.25, 0.25, 0.25),
            "target_background_policy": "explicit_target_background_v1",
            "invented": "field",
        },
        {
            "schema_version": "motif-conversion/v2",
            "method": "probability_matrix_target_background_v1",
            "prior_weight": 0.1,
            "source_motif_id": "source_model",
            "source_background": (0.4, 0.1, 0.2, 0.4),
            "target_background": (0.25, 0.25, 0.25, 0.25),
            "target_background_policy": "explicit_target_background_v1",
        },
    ],
)
def test_probability_matrix_target_background_conversion_rejects_malformed_contract(
    conversion: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        MotifConversion.model_validate(conversion)


def test_probability_matrix_target_background_conversion_rejects_model_disagreement() -> None:
    conversion = MotifConversion(
        schema_version="motif-conversion/v2",
        method="probability_matrix_target_background_v1",
        prior_weight=0.1,
        source_motif_id="source_model",
        source_background=(0.4, 0.1, 0.2, 0.3),
        target_background=(0.25, 0.25, 0.25, 0.25),
        target_background_policy="explicit_target_background_v1",
    )

    with pytest.raises(ValidationError, match="target background must equal model background"):
        MotifModel(
            motif_id="disagrees",
            probabilities=((0.7, 0.1, 0.1, 0.1),),
            background=(0.4, 0.1, 0.2, 0.3),
            conversion=conversion,
        )


@pytest.mark.parametrize(
    "conversion",
    [
        {
            "schema_version": "motif-conversion/v2",
            "method": "count_matrix_sqrt_n_background_prior_v1",
            "prior_weight": 0.1,
            "source_motif_id": "MA0001.1",
            "position_observed_counts": (4.0,),
            "position_prior_masses": (2.0,),
            "position_denominators": (6.0,),
        },
        {
            "schema_version": "motif-conversion/v2",
            "method": "count_matrix_sqrt_n_background_prior_v1",
            "source_motif_id": "MA0001.1",
            "position_observed_counts": (4.0,),
        },
        {
            "schema_version": "motif-conversion/v2",
            "method": "count_matrix_sqrt_n_background_prior_v1",
            "source_motif_id": "MA0001.1",
            "position_observed_counts": (4.0,),
            "position_prior_masses": (1.0,),
            "position_denominators": (5.0,),
        },
        {
            "schema_version": "motif-conversion/v2",
            "method": "count_matrix_sqrt_n_background_prior_v1",
            "source_motif_id": "MA0001.1",
            "position_observed_counts": (4.0,),
            "position_prior_masses": (2.0,),
            "position_denominators": (7.0,),
        },
        {
            "schema_version": "motif-conversion/v2",
            "method": "count_matrix_sqrt_n_background_prior_v1",
            "source_motif_id": "MA0001.1",
            "position_observed_counts": (),
            "position_prior_masses": (),
            "position_denominators": (),
        },
    ],
)
def test_count_matrix_conversion_rejects_incoherent_metadata(
    conversion: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        MotifConversion.model_validate(conversion)


@pytest.mark.parametrize(
    "conversion",
    [
        {
            "method": "jaspar_counts_to_probabilities_v1",
            "prior_weight": 0.1,
            "position_observed_counts": (4.0,),
        },
        {"method": "jaspar_counts_to_probabilities_v1"},
    ],
)
def test_historical_conversion_rejects_count_metadata_or_missing_weight(
    conversion: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        MotifConversion.model_validate(conversion)


def test_conversion_schema_versions_do_not_advertise_each_others_methods() -> None:
    with pytest.raises(ValidationError, match="requires motif-conversion/v2"):
        MotifConversion(
            method="count_matrix_sqrt_n_background_prior_v1",
            source_motif_id="MA0001.1",
            position_observed_counts=(4.0,),
            position_prior_masses=(2.0,),
            position_denominators=(6.0,),
        )

    with pytest.raises(ValidationError, match="does not admit the declared conversion method"):
        MotifConversion(
            schema_version="motif-conversion/v2",
            method="probability_matrix_prior_mixture_v1",
            prior_weight=0.1,
            source_motif_id="MA0001.1",
        )


def test_count_conversion_metadata_uses_an_ulp_bound_not_relative_scale() -> None:
    observed = 1.0e15
    prior = math.sqrt(observed)
    with pytest.raises(ValidationError, match="denominator"):
        MotifConversion(
            schema_version="motif-conversion/v2",
            method="count_matrix_sqrt_n_background_prior_v1",
            source_motif_id="MA0001.1",
            position_observed_counts=(observed,),
            position_prior_masses=(prior,),
            position_denominators=(observed + prior + 999.0,),
        )


def test_new_conversion_fields_do_not_change_historical_conversion_bytes() -> None:
    conversion = MotifConversion(
        method="probability_matrix_prior_mixture_v1",
        prior_weight=0.1,
        source_motif_id="source_cpxR",
    )

    assert conversion.model_dump(mode="json") == {
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
