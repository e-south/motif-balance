"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_explicit_search_methods.py

Requested methods remain explicit even when the budget covers a tiny space.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import pytest

from motif_balance import design
from motif_balance.api import design_observed, read_search_observation
from motif_balance.artifacts.verification import verify_portfolio_record
from motif_balance.compile import compile_design, planned_search_kind
from motif_balance.model.search_observation import ObservationSpec
from motif_balance.search import search
from tests.contract.test_search_observation import _spec


@pytest.mark.parametrize("method", ["annealed", "greedy", "random"])
@pytest.mark.parametrize("budget", [15, 16, 19])
def test_requested_method_spends_budget_without_claiming_enumeration(method, budget):
    spec = _spec(length=2, evaluations=budget, count=1)
    result, observation = design_observed(spec, ObservationSpec(), method=method)
    assert result.manifest.search_engine != "exhaustive_v1"
    assert result.manifest.completion_status == "budget_exhausted"
    assert result.manifest.exact_completion_status == "not_exact"
    assert result.manifest.evaluation_count == budget
    assert result.manifest.unique_evaluations <= min(budget, 16)
    assert result.manifest.search_engine_version == "2"
    if method != "random":
        assert sum(row.attempted for row in observation.moves) > 0
        assert len(observation.snapshots[0].states) == 8
    assert result == design(spec, method=method)
    assert read_search_observation(observation.model_dump_json().encode()) == observation
    verify_portfolio_record(result)


def test_default_and_preflight_are_annealed_regardless_of_space_size():
    spec = _spec(length=2, evaluations=19, count=1)
    assert planned_search_kind(spec) == "annealed"
    assert search(compile_design(spec)).completion_status == "budget_exhausted"


def test_exhaustive_is_an_explicit_opt_in_and_still_verifies():
    spec = _spec(length=2, evaluations=19, count=1)
    result, observation = design_observed(spec, ObservationSpec(), method="exhaustive")
    assert result.manifest.search_engine == "exhaustive_v1"
    assert result.manifest.search_engine_version == "1"
    assert result.manifest.evaluation_count == result.manifest.unique_evaluations == 16
    assert result.manifest.exact_completion_status == "complete"
    # AC and GT require opposite bases at both positions. Each can get one
    # preferred base, attaining one half; no base can satisfy both at once.
    assert result.manifest.best_observed.balance_score == pytest.approx(0.5)
    assert read_search_observation(observation.model_dump_json().encode()) == observation
    verify_portfolio_record(result)


def test_explicit_exhaustive_refuses_an_insufficient_budget():
    with pytest.raises(ValueError, match="budget covering"):
        design(_spec(length=2, evaluations=15, count=1), method="exhaustive")
