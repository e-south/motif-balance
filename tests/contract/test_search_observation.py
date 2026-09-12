"""Observing a search must not change the experiment being observed."""

from __future__ import annotations

import pytest

from motif_balance import DesignSpec, MotifModel, MotifSpecification, design
from motif_balance.api import design_observed, read_search_observation, verify_search_observation
from motif_balance.model.search_observation import ObservationSpec, SearchObservation


def _spec(*, length: int = 7, evaluations: int = 127, count: int = 2) -> DesignSpec:
    motifs = (
        MotifModel(
            motif_id="synthetic_left",
            probabilities=((0.7, 0.1, 0.1, 0.1), (0.1, 0.7, 0.1, 0.1)),
            background=(0.25, 0.25, 0.25, 0.25),
        ),
        MotifModel(
            motif_id="synthetic_right",
            probabilities=((0.1, 0.1, 0.7, 0.1), (0.1, 0.1, 0.1, 0.7)),
            background=(0.25, 0.25, 0.25, 0.25),
        ),
    )
    return DesignSpec(
        schema_version="design-spec/v3",
        specifications=tuple(MotifSpecification(motif=m, direction="seek") for m in motifs),
        length=length,
        evaluations=evaluations,
        count=count,
        strands="forward",
        seed=19,
    )


@pytest.mark.parametrize("length,evaluations", [(7, 127), (2, 16)])
def test_observation_preserves_complete_portfolio_and_replays(length, evaluations) -> None:
    spec = _spec(length=length, evaluations=evaluations)
    expected = design(spec)
    actual, observation = design_observed(
        spec, ObservationSpec(max_snapshots=6, score_targets=(0.0, 0.5, 1.0))
    )

    assert actual == expected
    assert observation.evaluation_count == evaluations
    assert 1 <= len(observation.snapshots) <= 6
    assert observation.snapshots[-1].evaluations == evaluations
    assert observation.snapshots[-1].incumbent == expected.manifest.best_observed
    assert observation.target_hits[0].first_evaluation == 1
    verify_search_observation(observation)
    assert SearchObservation.model_validate_json(observation.model_dump_json()) == observation


@pytest.mark.parametrize("initialization", ["related", "independent"])
def test_observation_preserves_every_evaluator_call_including_repeated_proposals(
    monkeypatch,
    initialization,
) -> None:
    from motif_balance.scoring import evaluate
    from motif_balance.search import engine, moves

    calls = []

    def recorded(sequence, problem):
        result = evaluate(sequence, problem)
        calls.append(result)
        return result

    monkeypatch.setattr(engine, "evaluate", recorded)
    monkeypatch.setattr(moves, "evaluate", recorded)
    expected = design(_spec(), initialization=initialization)
    baseline_calls = tuple(calls)
    calls.clear()
    actual, _ = design_observed(
        _spec(), ObservationSpec(max_snapshots=8), initialization=initialization
    )
    assert tuple(calls) == baseline_calls
    assert actual == expected


def test_observation_distinguishes_move_counts_and_keeps_chain_identity() -> None:
    _, observed = design_observed(_spec(), ObservationSpec(max_snapshots=8))
    assert all(
        tuple(s.chain_id for s in frame.states) == tuple(range(8)) for frame in observed.snapshots
    )
    assert sum(row.attempted for row in observed.moves) > 0
    assert all(row.changed <= row.accepted <= row.attempted for row in observed.moves)
    assert observed.snapshots[0].evaluations == 8
    assert observed.snapshots[-1].evaluations == 127


def test_unselected_proposal_updates_incumbent_and_exact_target_hit() -> None:
    from unittest.mock import Mock

    import numpy as np

    from motif_balance.compile import compile_design
    from motif_balance.scoring import evaluate
    from motif_balance.search.moves import SearchMoves
    from motif_balance.search.observation import SearchRecorder
    from motif_balance.search.recording import _SearchLedger

    motif = MotifModel(
        motif_id="synthetic_g",
        probabilities=((0.1, 0.1, 0.7, 0.1),),
        background=(0.25, 0.25, 0.25, 0.25),
    )
    spec = DesignSpec(
        schema_version="design-spec/v3",
        specifications=(MotifSpecification(motif=motif, direction="seek"),),
        length=1,
        evaluations=5,
        count=1,
        strands="forward",
        seed=19,
    )
    problem = compile_design(spec)
    observer = SearchRecorder(spec, ObservationSpec(max_snapshots=2, score_targets=(1.0,)))
    ledger = _SearchLedger(budget=5, directional=True, observer=observer)
    current = evaluate("T", problem)
    ledger.record(current)
    observer.snapshot(1, ledger.best_evaluation, (current,), force=True)
    rng = Mock(spec=np.random.Generator)
    rng.random.return_value = 1.0
    rng.integers.return_value = 0
    rng.choice.return_value = 3  # Keep T after scoring A, C, G, T, in that order.

    _, selected, accepted = SearchMoves()._single_move(
        problem,
        state=np.asarray([3], dtype=np.int8),
        current=current,
        rng=rng,
        ledger=ledger,
        progress=0.2,
    )
    observer.snapshot(ledger.evaluations_used, ledger.best_evaluation, (selected,), force=True)

    assert accepted and selected.sequence == "T" and selected.balance_score == 0.0
    assert ledger.evaluations_used == 5
    assert observer.hits == {1.0: 4}  # Initial T, then A, C, and the unselected G.
    frame = observer.frames[-1]
    assert frame.incumbent.sequence == "G" and frame.incumbent.balance_score == 1.0
    assert frame.states[0].evaluation == selected


def test_observation_refuses_unknown_fields_and_invalid_limits() -> None:
    for payload in (
        {"max_snapshots": 1},
        {"max_snapshots": 257},
        {"score_targets": (0.8, 0.5)},
        {"silent": True},
    ):
        with pytest.raises(ValueError):
            ObservationSpec.model_validate(payload)


def test_observation_rejects_fabricated_hit_time() -> None:
    _, observed = design_observed(_spec(), ObservationSpec(score_targets=(0.0,)))
    payload = observed.model_dump(mode="python")
    payload["target_hits"][0]["first_evaluation"] = 2
    corrupted = SearchObservation.model_validate(payload)
    with pytest.raises(ValueError, match="replay"):
        verify_search_observation(corrupted)


@pytest.mark.parametrize("budget", [1, 2, 7, 8, 9, 13, 128])
@pytest.mark.parametrize("capacity", [2, 3, 4, 16])
def test_snapshot_capacity_is_respected_even_at_tiny_budgets(budget, capacity) -> None:
    spec = _spec(evaluations=budget, count=1)
    _, observed = design_observed(spec, ObservationSpec(max_snapshots=capacity))
    assert len(observed.snapshots) <= capacity
    assert observed.snapshots[-1].evaluations == budget


def test_observation_byte_reader_refuses_oversize_unknown_and_modified_records() -> None:
    with pytest.raises(ValueError, match="byte limit"):
        read_search_observation(b" " * (64 * 1024 * 1024 + 1))
    _, observed = design_observed(_spec(), ObservationSpec(max_snapshots=2))
    assert read_search_observation(observed.model_dump_json().encode()) == observed
    payload = observed.model_dump(mode="json")
    payload["schema_version"] = "search-observation/unknown"
    import json

    with pytest.raises(ValueError):
        read_search_observation(json.dumps(payload).encode())


def test_large_observation_is_refused_before_any_search(monkeypatch) -> None:
    from motif_balance.search import AnnealedSearchEngine

    def forbidden(*args, **kwargs):
        pytest.fail("observation admission must precede search")

    monkeypatch.setattr(AnnealedSearchEngine, "search", forbidden)
    with pytest.raises(ValueError, match="snapshot base limit"):
        design_observed(_spec(length=1000, evaluations=10), ObservationSpec(max_snapshots=256))


@pytest.mark.parametrize("kind", ["chain", "budget", "score", "length", "targets", "moves"])
def test_observation_rejects_structural_corruption(kind) -> None:
    _, observed = design_observed(_spec(), ObservationSpec(max_snapshots=4, score_targets=(0.0,)))
    payload = observed.model_dump(mode="python")
    if kind == "chain":
        payload["snapshots"][-1]["states"][0]["chain_id"] = 20
    elif kind == "budget":
        payload["evaluation_count"] += 1
    elif kind == "score":
        payload["snapshots"][-1]["incumbent"]["balance_score"] = 5.0
    elif kind == "length":
        payload["snapshots"][-1]["incumbent"]["sequence"] += "A"
    elif kind == "targets":
        payload["target_hits"] = ()
    else:
        payload["moves"][0]["changed"] = 1000
    with pytest.raises(ValueError):
        SearchObservation.model_validate(payload)
