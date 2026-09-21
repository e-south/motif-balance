"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_search_incumbents.py

Exact incumbent receipts observe evaluator calls, not invented chain states.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import pytest

from motif_balance import DesignSpec, MotifModel, MotifSpecification, design, score
from motif_balance.api import design_observed, read_search_observation, verify_search_observation
from motif_balance.model.search_observation import ObservationSpec, SearchObservation


def _request(*, length=7, evaluations=127, second_direction="seek") -> DesignSpec:
    return DesignSpec(
        schema_version="design-spec/v3",
        specifications=tuple(
            MotifSpecification(
                motif=MotifModel(
                    motif_id=name,
                    probabilities=(probabilities,),
                    background=(0.25, 0.25, 0.25, 0.25),
                ),
                direction=second_direction if name == "synthetic_c" else "seek",
            )
            for name, probabilities in (
                ("synthetic_a", (0.7, 0.1, 0.1, 0.1)),
                ("synthetic_c", (0.1, 0.7, 0.1, 0.1)),
            )
        ),
        length=length,
        evaluations=evaluations,
        count=1,
        strands="both",
        seed=19,
    )


@pytest.mark.parametrize(
    "method,initialization",
    [
        ("annealed", "related"),
        ("annealed", "independent"),
        ("greedy", "related"),
        ("greedy", "independent"),
        ("random", "related"),
    ],
)
@pytest.mark.parametrize("second_direction", ["seek", "avoid"])
def test_exact_incumbents_match_call_prefixes_without_changing_any_search_call(
    monkeypatch,
    method,
    initialization,
    second_direction,
) -> None:
    from motif_balance.scoring import evaluate
    from motif_balance.search import engine, greedy, moves, uniform
    from motif_balance.search import initialization as starts

    calls = []

    def recorded(sequence, problem):
        result = evaluate(sequence, problem)
        calls.append(result)
        return result

    for module in (engine, greedy, starts, moves, uniform):
        monkeypatch.setattr(module, "evaluate", recorded)
    spec = _request(second_direction=second_direction)
    expected = design(spec, method=method, initialization=initialization)
    baseline = tuple(calls)
    calls.clear()
    requested = (1, 4, 8, 16, 63, 127)
    actual, observed = design_observed(
        spec,
        ObservationSpec(max_snapshots=4, incumbent_evaluations=requested),
        method=method,
        initialization=initialization,
    )
    assert actual == expected
    assert tuple(calls) == baseline
    assert len(baseline) == spec.evaluations
    assert tuple(row.evaluations for row in observed.incumbents) == requested
    for row in observed.incumbents:
        # Independent directional max-min oracle with literal tie breaking.
        incumbent = min(
            baseline[: row.evaluations], key=lambda item: (-item.balance_score, item.sequence)
        )
        assert row.incumbent == incumbent == score(incumbent.sequence, spec)
    assert observed.incumbents[-1].incumbent == actual.manifest.best_observed
    verify_search_observation(observed)
    assert read_search_observation(observed.model_dump_json().encode()) == observed


def test_exact_control_marks_unreached_call_instead_of_repeating_final_sequence() -> None:
    _, observed = design_observed(
        _request(length=2, evaluations=32),
        ObservationSpec(incumbent_evaluations=(1, 16, 17, 32)),
    )
    assert observed.evaluation_count == 16
    assert observed.incumbents[1].incumbent == observed.snapshots[-1].incumbent
    assert [row.incumbent for row in observed.incumbents[2:]] == [None, None]
    verify_search_observation(observed)


@pytest.mark.parametrize("counts", [(0,), (True,), (1.0,), (4, 1), (1, 1), tuple(range(1, 34))])
def test_invalid_incumbent_requests_fail_closed(counts) -> None:
    with pytest.raises(ValueError):
        ObservationSpec(incumbent_evaluations=counts)


def test_incumbent_beyond_requested_budget_is_refused_before_search(monkeypatch) -> None:
    from motif_balance.search import AnnealedSearchEngine

    def forbidden(*args, **kwargs):
        pytest.fail("invalid observation reached search")

    monkeypatch.setattr(AnnealedSearchEngine, "search", forbidden)
    with pytest.raises(ValueError, match=r"incumbent.*budget"):
        design_observed(_request(), ObservationSpec(incumbent_evaluations=(128,)))


@pytest.mark.parametrize(
    "corruption", ["missing", "count", "null", "future", "length", "final", "budget"]
)
def test_exact_incumbent_structure_is_validated(corruption) -> None:
    _, observed = design_observed(
        _request(length=2, evaluations=32),
        ObservationSpec(incumbent_evaluations=(1, 16, 32)),
    )
    payload = observed.model_dump(mode="python")
    if corruption == "missing":
        del payload["incumbents"]
    elif corruption == "count":
        payload["incumbents"][0]["evaluations"] = 2
    elif corruption == "null":
        payload["incumbents"][0]["incumbent"] = None
    elif corruption == "future":
        payload["incumbents"][-1]["incumbent"] = payload["incumbents"][1]["incumbent"]
    elif corruption == "length":
        payload["incumbents"][0]["incumbent"]["sequence"] += "A"
    elif corruption == "final":
        payload["incumbents"][1]["incumbent"] = payload["incumbents"][0]["incumbent"]
    else:
        payload["observation_spec"]["incumbent_evaluations"] = (1, 16, 33)
        payload["incumbents"][-1]["evaluations"] = 33
    with pytest.raises(ValueError):
        SearchObservation.model_validate(payload)


def test_plausible_but_false_exact_incumbent_is_rejected_by_replay() -> None:
    spec = _request()
    _, observed = design_observed(
        spec, ObservationSpec(max_snapshots=2, incumbent_evaluations=(16,))
    )
    payload = observed.model_dump(mode="python")
    original = observed.incumbents[0].incumbent
    assert original is not None
    alternatives = [score(word, spec) for word in ("AAAAAAC", "AAAAACA", "AAAACAA")]
    replacement = next(row for row in alternatives if row.sequence != original.sequence)
    assert replacement.balance_score == original.balance_score
    payload["incumbents"][0]["incumbent"] = replacement.model_dump(mode="python")
    corrupted = SearchObservation.model_validate(payload)
    with pytest.raises(ValueError, match="replay"):
        verify_search_observation(corrupted)


@pytest.mark.parametrize("schema", ["search-observation/v1", "search-observation/v2"])
def test_reader_does_not_adapt_superseded_observation_schemas(schema) -> None:
    _, observed = design_observed(_request(), ObservationSpec())
    assert observed.schema_version == "search-observation/v4"
    payload = observed.model_dump(mode="python")
    payload["schema_version"] = schema
    with pytest.raises(ValueError):
        SearchObservation.model_validate(payload)


def test_exact_incumbents_are_included_in_pre_search_size_admission(monkeypatch) -> None:
    from motif_balance.search import AnnealedSearchEngine

    def forbidden(*args, **kwargs):
        pytest.fail("oversized exact observations reached search")

    monkeypatch.setattr(AnnealedSearchEngine, "search", forbidden)
    with pytest.raises(ValueError, match="snapshot base limit"):
        design_observed(
            _request(length=1000),
            ObservationSpec(max_snapshots=110, incumbent_evaluations=tuple(range(1, 33))),
        )
