"""Initialization choices are explicit, budget-matched, and replayable."""

from __future__ import annotations

import pytest

from motif_balance import design
from motif_balance.api import design_observed, read_search_observation
from motif_balance.artifacts import read_verified_portfolio
from motif_balance.model.search_observation import ObservationSpec
from tests.contract.test_search_observation import _spec


def test_independent_starts_preserve_budget_and_have_distinct_replayable_identity(tmp_path):
    spec = _spec(length=20, evaluations=127, count=1)
    policy = ObservationSpec(max_snapshots=4, quality_thresholds=(0.5,))
    baseline, related = design_observed(spec, policy)
    expected = design(spec, initialization="independent")
    actual, independent = design_observed(spec, policy, initialization="independent")

    assert design(spec, initialization="related") == baseline
    assert actual == expected
    assert actual.problem_id == baseline.problem_id
    assert actual.run_id != baseline.run_id
    assert actual.manifest.search_engine == independent.engine == "annealed_independent_starts_v1"
    assert independent.engine_version == "1"
    assert independent.evaluation_count == related.evaluation_count == 127
    assert independent.snapshots[0].evaluations == related.snapshots[0].evaluations == 8
    assert len(independent.snapshots[0].states) == 8
    starts = [row.evaluation.sequence for row in independent.snapshots[0].states]
    assert any(sum(a != b for a, b in zip(starts[0], s, strict=True)) > 5 for s in starts[1:])
    assert starts != [row.evaluation.sequence for row in related.snapshots[0].states]
    assert read_search_observation(independent.model_dump_json().encode()) == independent
    actual.write(tmp_path / "independent")
    assert read_verified_portfolio(tmp_path / "independent").model_dump() == actual.model_dump()


def test_initialization_does_not_change_complete_enumeration():
    spec = _spec(length=2, evaluations=16)
    related, a = design_observed(spec, ObservationSpec())
    independent, b = design_observed(spec, ObservationSpec(), initialization="independent")
    assert related == independent and a == b
    assert independent.manifest.search_engine == "exhaustive_v1"


@pytest.mark.parametrize("initialization", ["unknown", "", None, 1])
def test_unknown_initialization_fails_before_search(initialization, monkeypatch):
    from motif_balance.search import AnnealedSearchEngine

    def forbidden(*args, **kwargs):
        pytest.fail("invalid initialization must fail before search")

    monkeypatch.setattr(AnnealedSearchEngine, "search", forbidden)
    with pytest.raises(ValueError, match="initialization"):
        design(_spec(), initialization=initialization)


def test_observation_replay_refuses_a_relabeled_method():
    _, observation = design_observed(_spec(), ObservationSpec())
    changed = observation.model_copy(update={"engine": "annealed_independent_starts_v1"})
    with pytest.raises(ValueError, match="replay"):
        read_search_observation(changed.model_dump_json().encode())


def test_independent_initialization_requires_directional_inputs():
    from motif_balance import DesignSpec
    from motif_balance.errors import IncompatibleDesign

    directional = _spec()
    spec = DesignSpec(
        motifs=tuple(s.motif for s in directional.specifications),
        length=7,
        evaluations=127,
        count=1,
        seed=directional.seed,
    )
    with pytest.raises(IncompatibleDesign, match="directional"):
        design(spec, initialization="independent")


@pytest.mark.parametrize(
    "engine,version", [("unknown", "1"), ("annealed_independent_starts_v1", "2")]
)
def test_unknown_recorded_method_is_rejected_before_replay(engine, version, monkeypatch):
    import motif_balance.api

    _, observation = design_observed(_spec(), ObservationSpec())
    changed = observation.model_copy(update={"engine": engine, "engine_version": version})

    def forbidden(*args, **kwargs):
        pytest.fail("unknown method identity must fail before replay")

    monkeypatch.setattr(motif_balance.api, "design_observed", forbidden)
    with pytest.raises(ValueError, match="unsupported"):
        read_search_observation(changed.model_dump_json().encode())


@pytest.mark.parametrize("budget", [1, 2, 7, 8, 9])
def test_independent_initialization_spends_tiny_budgets_exactly(budget):
    _, observation = design_observed(
        _spec(evaluations=budget, count=1), ObservationSpec(), initialization="independent"
    )
    assert observation.evaluation_count == budget
    assert len(observation.snapshots[0].states) == min(budget, 8)
