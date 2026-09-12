"""The explicit greedy comparator preserves scoring, budgets, and replay identity."""

from __future__ import annotations

import pytest

from motif_balance import design, score
from motif_balance.api import design_observed, read_search_observation
from motif_balance.artifacts import read_verified_portfolio
from motif_balance.model.search_observation import ObservationSpec
from tests.contract.test_search_observation import _spec


@pytest.mark.parametrize("initialization", ["related", "independent"])
def test_greedy_is_budget_matched_initialized_equally_and_replayable(tmp_path, initialization):
    spec = _spec(length=20, evaluations=127, count=1)
    policy = ObservationSpec(max_snapshots=12, quality_thresholds=(0.5,))
    baseline, annealed = design_observed(spec, policy, initialization=initialization)
    result, greedy = design_observed(spec, policy, method="greedy", initialization=initialization)
    assert design(spec, method="greedy", initialization=initialization) == result
    assert greedy.evaluation_count == annealed.evaluation_count == 127
    assert greedy.snapshots[0].states == annealed.snapshots[0].states
    assert result.problem_id == baseline.problem_id and result.run_id != baseline.run_id
    assert greedy.engine == (
        "greedy_multistart_v1" if initialization == "related" else "greedy_independent_starts_v1"
    )
    assert greedy.engine == result.manifest.search_engine
    for previous, current in zip(greedy.snapshots[:-1], greedy.snapshots[1:], strict=True):
        assert all(
            b.evaluation.balance_score >= a.evaluation.balance_score
            for a, b in zip(previous.states, current.states, strict=True)
        )
    moves = {row.move: row for row in greedy.moves}
    assert moves["single"].attempted == 30
    assert moves["single"].accepted == moves["single"].changed == moves["single"].improved
    assert moves["single"].decreased == 0
    assert all(moves[move].attempted == 0 for move in ("block", "multi", "insertion"))
    for elite in result.manifest.elites:
        assert score(elite.sequence, spec) == elite
    assert read_search_observation(greedy.model_dump_json().encode()) == greedy
    result.write(tmp_path / "greedy")
    assert read_verified_portfolio(tmp_path / "greedy").model_dump() == result.model_dump()


@pytest.mark.parametrize("budget", [1, 2, 7, 8, 9, 10, 11, 12, 127])
def test_greedy_spends_the_exact_budget_including_partial_final_trials(budget):
    result, observation = design_observed(
        _spec(evaluations=budget, count=1), ObservationSpec(), method="greedy"
    )
    assert observation.evaluation_count == result.manifest.evaluation_count == budget
    assert len(observation.snapshots[0].states) == min(budget, 8)


def test_greedy_selection_does_not_replace_complete_enumeration():
    spec = _spec(length=2, evaluations=16)
    ordinary, expected = design_observed(spec, ObservationSpec())
    alternative, actual = design_observed(spec, ObservationSpec(), method="greedy")
    assert alternative == ordinary and actual == expected
    assert actual.engine == "exhaustive_v1"


@pytest.mark.parametrize("method", ["unknown", "", None, 1])
def test_unknown_method_fails_before_scoring(method, monkeypatch):
    import motif_balance.api

    monkeypatch.setattr(
        motif_balance.api,
        "compile_design",
        lambda *_: pytest.fail("invalid method reached compilation"),
    )
    with pytest.raises(ValueError, match="method"):
        design(_spec(), method=method)


def test_greedy_relabeling_cannot_pass_observation_replay():
    _, observation = design_observed(_spec(), ObservationSpec())
    relabeled = observation.model_copy(update={"engine": "greedy_multistart_v1"})
    with pytest.raises(ValueError, match="replay"):
        read_search_observation(relabeled.model_dump_json().encode())


def test_neutral_trials_keep_the_current_state_but_still_consume_budget():
    from motif_balance import DesignSpec, MotifModel, MotifSpecification

    models = tuple(
        MotifModel(
            schema_version="motif-model/v2",
            motif_id=name,
            probabilities=((0.7, 0.1, 0.1, 0.1),),
            background=(0.25,) * 4,
        )
        for name in ("a", "b")
    )
    # Attainment is 0 or 1 for this word model; min(a, 1-a) is always zero.
    spec = DesignSpec(
        schema_version="design-spec/v3",
        specifications=(
            MotifSpecification(motif=models[0], direction="seek"),
            MotifSpecification(motif=models[1], direction="avoid"),
        ),
        length=7,
        count=1,
        evaluations=127,
        seed=13,
        strands="forward",
    )
    result, observation = design_observed(spec, ObservationSpec(), method="greedy")
    assert observation.snapshots[-1].states == observation.snapshots[0].states
    assert result.manifest.best_observed.balance_score == 0
    assert result.manifest.evaluation_count == 127
    assert result.manifest.unique_evaluations < 127
    assert observation.moves[0].accepted == observation.moves[0].changed == 0


def test_greedy_refuses_legacy_constraints_before_evaluation(monkeypatch):
    import motif_balance.search.greedy
    from motif_balance import DesignSpec
    from motif_balance.errors import IncompatibleDesign

    directional = _spec()
    spec = DesignSpec(
        motifs=tuple(s.motif for s in directional.specifications),
        length=7,
        evaluations=127,
        count=1,
        seed=7,
    )
    monkeypatch.setattr(
        motif_balance.search.greedy,
        "evaluate",
        lambda *_: pytest.fail("legacy request was evaluated"),
    )
    with pytest.raises(IncompatibleDesign, match="directional"):
        design(spec, method="greedy")
