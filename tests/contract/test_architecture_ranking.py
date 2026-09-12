"""Public architecture ranking starts from supplied sequences, never a search."""

from itertools import product
from pathlib import Path

import pytest
from pydantic import ValidationError

from motif_balance import DesignSpec, MotifModel, MotifSpecification


def specification(*, length=2, strands="forward"):
    return DesignSpec(
        schema_version="design-spec/v3",
        specifications=tuple(
            MotifSpecification(
                motif=MotifModel(
                    motif_id=name,
                    probabilities=(tuple(0.7 if base == preferred else 0.1 for base in "ACGT"),),
                    background=(0.25,) * 4,
                ),
                direction="seek",
            )
            for name, preferred in (("a", "A"), ("b", "C"))
        ),
        length=length,
        count=1,
        strands=strands,
        seed=7,
        evaluations=1,
    )


def test_every_recovered_architecture_has_a_quality_rank_and_a_selectable_representative():
    from motif_balance.alternatives import rank_architectures

    words = tuple("".join(word) for word in product("ACGT", repeat=2))
    result = rank_architectures(words, specification())
    # Literal oracle: only AC and CA contain both preferred bases. Their two
    # orders are distinct; all other words share the zero-score overlap class.
    assert [r.evaluation.sequence for r in result.representatives] == ["AC", "CA", "AA"]
    assert [r.minimum_balance for r in result.prefixes] == [1.0, 1.0, 0.0]
    assert [r.architecture_count for r in result.quality_steps] == [2, 3]
    assert [e.sequence for e in result.select(2)] == ["AC", "CA"]
    assert result.prefixes[0].mean_sequence_distance is None
    assert result.prefixes[1].mean_sequence_distance == 1.0
    assert result.prefixes[1].mean_selected_footprint_distance == 1.0
    assert result.prefixes[1].mean_spacing_distance_nt == 0.0
    assert result.prefixes[1].mean_orientation_difference == 0.0
    assert result.input_records == result.literal_sequences == result.sequence_classes == 16
    assert result.scoring_evaluations == 16
    assert result.search_evaluations == 0
    assert result == rank_architectures(tuple(reversed(words)), specification())


@pytest.mark.parametrize("count", [1, 2, 17])
def test_pool_ranking_does_not_apply_the_original_portfolio_count(count):
    from motif_balance.alternatives import rank_architectures

    spec = DesignSpec.model_validate(
        {**specification().model_dump(mode="python"), "count": count, "evaluations": 17}
    )
    result = rank_architectures(("AC", "CA"), spec)
    assert result.spec == spec
    assert [item.sequence for item in result.select(2)] == ["AC", "CA"]
    assert [item.balance_score for item in result.select(2)] == [1.0, 1.0]
    assert result.scoring_evaluations == 2
    assert result.search_evaluations == 0


def test_impossible_portfolio_count_still_fails_before_design_compiles_motifs(monkeypatch):
    from motif_balance import compile as compilation
    from motif_balance import design
    from motif_balance.errors import IncompatibleDesign

    spec = DesignSpec.model_validate(
        {**specification().model_dump(mode="python"), "count": 17, "evaluations": 17}
    )
    monkeypatch.setattr(
        compilation, "_compile_motif", lambda *_: pytest.fail("infeasible design compiled motifs")
    )
    with pytest.raises(IncompatibleDesign, match="count exceeds the complete sequence space"):
        design(spec)


def test_pool_ranking_still_rejects_wide_motifs_before_matrix_compilation(monkeypatch):
    from motif_balance import compile as compilation
    from motif_balance.alternatives import rank_architectures
    from motif_balance.errors import IncompatibleDesign

    payload = specification(length=1).model_dump(mode="python")
    payload["specifications"][0]["motif"]["probabilities"] *= 2
    spec = DesignSpec.model_validate(payload)
    monkeypatch.setattr(
        compilation, "_compile_motif", lambda *_: pytest.fail("incompatible width compiled")
    )
    with pytest.raises(IncompatibleDesign, match="wider"):
        rank_architectures(("A",), spec)


def test_information_architecture_names_the_current_ranking_schema():
    from motif_balance.model.alternatives import ArchitectureRanking

    authority = (Path(__file__).resolve().parents[2] / "IA.md").read_text()
    row = next(line for line in authority.splitlines() if "| alternatives |" in line)
    schema = ArchitectureRanking.model_fields["schema_version"].default
    assert row.endswith(f"`{schema}` |")


@pytest.mark.parametrize("count", [0, -1, True, "2", 1.5, 4])
def test_selection_never_relaxes_an_unsupported_count(count):
    from motif_balance.alternatives import rank_architectures

    result = rank_architectures(("AC", "CA"), specification())
    with pytest.raises(ValueError, match="count must"):
        result.select(count)


@pytest.mark.parametrize(
    "words", ["AC", iter(["AC"]), [None], ["ac"], ["AN"], ["A"], ["AC"] * 50_001]
)
def test_bad_pools_fail_before_compilation(words, monkeypatch):
    from motif_balance.alternatives import api

    def forbidden(*args, **kwargs):
        pytest.fail("invalid pool reached compilation")

    monkeypatch.setattr(api, "compile_scoring", forbidden)
    with pytest.raises(ValueError, match=r"pool|sequence"):
        api.rank_architectures(words, specification())


def test_scoring_work_is_admitted_before_compilation(monkeypatch):
    from motif_balance.alternatives import api

    monkeypatch.setattr(api, "MAX_SCORE_BASE_OPERATIONS", 1, raising=False)
    monkeypatch.setattr(api, "compile_scoring", lambda *_: pytest.fail("over-budget pool compiled"))
    with pytest.raises(ValueError, match="scoring"):
        api.rank_architectures(("AC",), specification())


def test_distance_work_is_admitted_before_pair_comparisons(monkeypatch):
    from motif_balance.alternatives import api

    monkeypatch.setattr(
        api, "pair_distances", lambda *_args, **_kwargs: pytest.fail("distance budget ignored")
    )
    monkeypatch.setattr(
        api, "prepare_distances", lambda *_args, **_kwargs: pytest.fail("over-budget pool prepared")
    )
    with pytest.raises(ValueError, match="distance"):
        api.rank_architectures(("AC", "CA"), specification(), distance_base_budget=1)


@pytest.mark.parametrize("fault", ["legacy", "one_motif", "distance_constraint"])
def test_unsupported_specifications_are_not_reinterpreted(fault):
    from motif_balance.alternatives import rank_architectures

    spec = specification()
    payload = spec.model_dump(mode="python")
    if fault == "legacy":
        payload = {
            "motifs": spec.scored_motifs,
            "length": 2,
            "count": 1,
            "evaluations": 1,
            "seed": 7,
        }
    elif fault == "one_motif":
        payload["specifications"] = payload["specifications"][:1]
    else:
        payload["min_distance"] = 0.5
    with pytest.raises(ValueError, match=r"directional|two|distance"):
        rank_architectures(("AC",), DesignSpec.model_validate(payload))


@pytest.mark.parametrize("fault", ["count", "rank", "quality", "classes", "diversity", "geometry"])
def test_ranked_records_reject_inconsistent_projections(fault):
    from motif_balance.alternatives import rank_architectures
    from motif_balance.model.alternatives import ArchitectureRanking

    result = rank_architectures(("AC", "CA"), specification())
    payload = result.model_dump(mode="python")
    if fault == "count":
        payload["scoring_evaluations"] = 10
    elif fault == "rank":
        payload["representatives"][0]["rank"] = 2
    elif fault == "quality":
        payload["prefixes"][0]["minimum_balance"] = 0.5
    elif fault == "classes":
        payload["representatives"][0]["sequence_classes"] = 2
    elif fault == "diversity":
        payload["prefixes"][0]["mean_sequence_distance"] = 0.0
    else:
        payload["representatives"][0]["geometry"] = (("b", 1000, "same"),)
    with pytest.raises(ValidationError):
        ArchitectureRanking.model_validate(payload)


def test_canonical_tie_replay_is_independent_of_which_strand_was_supplied():
    from motif_balance.alternatives import rank_architectures

    spec = specification(length=4, strands="both")
    base = rank_architectures(("TGGT", "ACCC"), spec)
    expanded = rank_architectures(("TGGT", "ACCC", "ACCA"), spec)
    assert base.representatives == expanded.representatives
    assert [e.sequence for e in base.select(1)] == ["ACCA"]
    assert base.literal_sequences == 2 and expanded.literal_sequences == 3
    assert base.sequence_classes == expanded.sequence_classes == 2
    assert base.scoring_evaluations == expanded.scoring_evaluations == 2
    assert base.spec == spec


def test_empty_pool_is_not_zero_optionality_or_a_completed_enumeration():
    from motif_balance.alternatives import rank_architectures

    result = rank_architectures((), specification())
    assert result.coverage == "supplied_pool"
    assert result.representatives == result.prefixes == result.quality_steps == ()
    assert result.scoring_evaluations == 0
    with pytest.raises(ValueError, match="does not support"):
        result.select(1)


def test_a_single_architecture_never_prepares_quadratic_motif_distances(monkeypatch):
    from motif_balance.alternatives import api

    monkeypatch.setattr(
        api, "prepare_distances", lambda *_: pytest.fail("one representative needs no distances")
    )
    result = api.rank_architectures(("AC",), specification())
    assert len(result.prefixes) == 1
    assert result.prefixes[0].mean_spacing_distance_nt is None


def test_explicit_distance_budget_is_recorded_and_checked():
    from motif_balance.alternatives import rank_architectures

    # Two length-two, two-motif representatives: one pair, 4 base terms + 2
    # ordered motif-pair terms. This is a declared work bound, not elapsed time.
    result = rank_architectures(("AC", "CA"), specification(), distance_base_budget=6)
    assert result.distance_base_budget == result.distance_base_operations == 6
    assert result.schema_version == "architecture-ranking/v2"
    with pytest.raises(ValueError, match="distance"):
        rank_architectures(("AC", "CA"), specification(), distance_base_budget=5)


@pytest.mark.parametrize("budget", [True, 0, -1, 1.5, "100", 500_000_001])
def test_invalid_explicit_distance_budgets_fail_before_compilation(budget, monkeypatch):
    from motif_balance.alternatives import api

    monkeypatch.setattr(api, "compile_scoring", lambda *_: pytest.fail("invalid budget compiled"))
    with pytest.raises(ValueError, match="distance budget"):
        api.rank_architectures(("AC",), specification(), distance_base_budget=budget)


@pytest.mark.parametrize(
    "limit", ["MAX_ARCHITECTURE_DISTANCE_PAIRS", "MAX_ARCHITECTURE_PREPARED_PAIRS"]
)
def test_explicit_budget_does_not_override_independent_pair_or_preparation_caps(limit, monkeypatch):
    from motif_balance.alternatives import api

    monkeypatch.setattr(api, limit, 0, raising=False)
    monkeypatch.setattr(api, "prepare_distances", lambda *_: pytest.fail("unadmitted preparation"))
    with pytest.raises(ValueError, match="distance"):
        api.rank_architectures(("AC", "CA"), specification(), distance_base_budget=500_000_000)


@pytest.mark.parametrize(
    "field,value", [("distance_base_budget", 5), ("distance_base_operations", 5)]
)
def test_serialized_distance_accounting_cannot_be_forged(field, value):
    from motif_balance.alternatives import rank_architectures
    from motif_balance.model.alternatives import ArchitectureRanking

    payload = rank_architectures(("AC", "CA"), specification()).model_dump(mode="python")
    payload[field] = value
    with pytest.raises(ValidationError, match="distance"):
        ArchitectureRanking.model_validate(payload)


def test_explicit_prefix_order_reuses_verified_representatives_without_rescoring(monkeypatch):
    from motif_balance.alternatives import api

    ranking = api.rank_architectures(("AC", "CA", "AA"), specification())
    monkeypatch.setattr(api, "evaluate", lambda *_: pytest.fail("prefix measurement rescored"))
    prefixes = api.measure_prefixes(ranking, ("AA", "AC", "CA"))
    assert [p.minimum_balance for p in prefixes] == [0, 0, 0]
    assert prefixes[1].mean_sequence_distance == 0.5
    assert prefixes[2].mean_sequence_distance == pytest.approx(2 / 3)
    assert prefixes[2].mean_spacing_distance_nt == pytest.approx(2 / 3)
    assert [r.evaluation.sequence for r in ranking.representatives] == ["AC", "CA", "AA"]
    assert api.measure_prefixes(ranking, ("AC", "CA", "AA")) is ranking.prefixes


@pytest.mark.parametrize("order", [("AC",), ("AC", "AC"), ("AC", "TT"), iter(("AC", "CA"))])
def test_prefix_order_must_include_exactly_the_complete_collection(order, monkeypatch):
    from motif_balance.alternatives import api

    ranking = api.rank_architectures(("AC", "CA"), specification())
    monkeypatch.setattr(api, "prepare_distances", lambda *_: pytest.fail("invalid order prepared"))
    with pytest.raises(ValueError, match="complete permutation"):
        api.measure_prefixes(ranking, order)


def test_nonempty_input_cannot_have_zero_sequence_classes():
    from motif_balance.alternatives import rank_architectures
    from motif_balance.model.alternatives import ArchitectureRanking

    payload = rank_architectures((), specification()).model_dump(mode="python")
    payload["input_records"] = 1
    with pytest.raises(ValidationError, match="counts disagree"):
        ArchitectureRanking.model_validate(payload)


def test_selection_returns_scored_objects_without_editing_inputs_or_rescoring(monkeypatch):
    from motif_balance.alternatives import api

    words = ["CA", "AC", "AC"]
    result = api.rank_architectures(words, specification())
    monkeypatch.setattr(api, "evaluate", lambda *_: pytest.fail("selection rescored a sequence"))
    selected = result.select(2)
    assert words == ["CA", "AC", "AC"]
    assert selected[0] is result.representatives[0].evaluation
    assert result.input_records == 3 and result.literal_sequences == 2
    assert result.scoring_evaluations == 2
    with pytest.raises(ValidationError, match="frozen"):
        selected[0].sequence = "TT"


@pytest.mark.parametrize("names", [("a", "b", "c"), ("z", "y", "x")])
def test_three_model_distances_have_literal_label_independent_meaning(names):
    from motif_balance.alternatives import rank_architectures

    base = specification(length=3)
    specs = tuple(
        MotifSpecification(
            motif=MotifModel(
                motif_id=name,
                probabilities=(tuple(0.7 if b == preferred else 0.1 for b in "ACGT"),),
                background=(0.25,) * 4,
            ),
            direction="seek",
        )
        for name, preferred in zip(names, "ACG", strict=True)
    )
    spec = DesignSpec.model_validate({**base.model_dump(mode="python"), "specifications": specs})
    result = rank_architectures(("ACG", "CAG"), spec)
    assert [e.sequence for e in result.select(2)] == ["ACG", "CAG"]
    last = result.prefixes[-1]
    assert last.minimum_balance == 1
    assert last.mean_sequence_distance == pytest.approx(2 / 3)
    assert last.mean_selected_footprint_distance == pytest.approx(2 / 3)
    assert last.mean_spacing_distance_nt == pytest.approx(2 / 3)
    assert last.mean_orientation_difference == 0


def test_directional_ranking_uses_the_strongest_unwanted_window():
    from motif_balance.alternatives import rank_architectures

    payload = specification().model_dump(mode="python")
    payload["specifications"][1]["direction"] = "avoid"
    result = rank_architectures(("AA", "AC", "TT"), DesignSpec.model_validate(payload))
    assert [e.sequence for e in result.select(2)] == ["AA", "AC"]
    assert [p.minimum_balance for p in result.prefixes] == [1, 0]
    unwanted = result.representatives[1].evaluation.matches[1]
    assert unwanted.start == 1 and unwanted.spec_satisfaction == 0


def test_ranked_records_round_trip_but_reject_untyped_and_unknown_fields():
    from motif_balance.alternatives import rank_architectures
    from motif_balance.model.alternatives import ArchitectureRanking

    result = rank_architectures(("AC", "CA"), specification())
    assert ArchitectureRanking.model_validate_json(result.model_dump_json()) == result
    for changes in (
        {"input_records": "2"},
        {"input_records": True},
        {"coverage": "complete_enumeration"},
        {"unknown": 1},
    ):
        with pytest.raises(ValidationError):
            ArchitectureRanking.model_validate({**result.model_dump(mode="python"), **changes})


def test_representative_matched_words_must_come_from_its_sequence():
    from motif_balance.alternatives import rank_architectures
    from motif_balance.model.alternatives import ArchitectureRanking

    payload = rank_architectures(("AC",), specification()).model_dump(mode="python")
    payload["representatives"][0]["evaluation"]["matches"][0]["matched_sequence"] = "C"
    with pytest.raises(ValidationError, match="matched word"):
        ArchitectureRanking.model_validate(payload)


@pytest.mark.parametrize("fault", ["strand_counts", "length", "spacing", "weakest", "order"])
def test_ranked_records_validate_cross_field_scientific_invariants(fault):
    from motif_balance.alternatives import rank_architectures
    from motif_balance.model.alternatives import ArchitectureRanking

    payload = rank_architectures(("AC", "CA"), specification()).model_dump(mode="python")
    if fault == "strand_counts":
        payload["input_records"] = payload["literal_sequences"] = 3
    elif fault == "length":
        payload["spec"]["length"] = 3
    elif fault == "spacing":
        payload["prefixes"][1]["mean_spacing_distance_nt"] = 3
    elif fault == "weakest":
        payload["representatives"][1]["evaluation"]["balance_score"] -= 1e-10
        payload["prefixes"][1]["minimum_balance"] -= 1e-10
    else:
        payload["representatives"] = tuple(reversed(payload["representatives"]))
        for rank, row in enumerate(payload["representatives"], 1):
            row["rank"] = rank
    with pytest.raises(ValidationError):
        ArchitectureRanking.model_validate(payload)
