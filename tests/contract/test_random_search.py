"""Uniform sampling is an explicit comparator with common scoring and retention."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from motif_balance import design, score
from motif_balance.api import design_observed, read_search_observation
from motif_balance.artifacts import read_verified_portfolio
from motif_balance.model.search_observation import ObservationSpec
from tests.contract.test_search_observation import _spec


@pytest.mark.parametrize("budget", [1, 7, 16, 31, 127])
def test_random_matches_independent_whole_sequence_draws_and_counts_repeats(tmp_path, budget):
    spec = _spec(length=2, evaluations=budget, count=1)
    policy = ObservationSpec(
        score_targets=(0.0, 0.5, 1.0), quality_thresholds=(0.0, 0.5), max_sequences_per_threshold=8
    )
    rng = np.random.Generator(np.random.PCG64(spec.seed))
    sequences = [
        "".join("ACGT"[int(base)] for base in rng.integers(0, 4, size=2, dtype=np.int8))
        for _ in range(budget)
    ]
    expected = [score(sequence, spec) for sequence in sequences]
    result, observed = design_observed(spec, policy, method="random")
    assert result == design(spec, method="random")
    assert result.manifest.search_engine == observed.engine == "uniform_random_v1"
    assert result.manifest.evaluation_count == budget
    assert result.manifest.unique_evaluations == len(set(sequences))
    assert result.manifest.exact_completion_status == "not_exact"
    assert result.manifest.completion_status == "budget_exhausted"
    assert result.manifest.best_observed == min(
        expected, key=lambda item: (-item.balance_score, item.sequence)
    )
    assert all(
        frame.states == () for frame in observed.snapshots
    )  # No fictitious local-search chain.
    assert all(move.attempted == 0 for move in observed.moves)
    for hit in observed.target_hits:
        assert hit.first_evaluation == next(
            (i + 1 for i, row in enumerate(expected) if row.balance_score >= hit.target), None
        )
    for sample in observed.quality_samples:
        qualifying = [row for row in expected if row.balance_score >= sample.threshold]
        unique = {row.sequence: row for row in qualifying}
        ordered = sorted(
            unique, key=lambda sequence: (hashlib.sha256(sequence.encode()).hexdigest(), sequence)
        )[:8]
        assert sample.qualifying_evaluations == len(qualifying)
        assert sample.unique_sequences == len(unique)
        assert sample.evaluations == tuple(unique[sequence] for sequence in ordered)
    assert read_search_observation(observed.model_dump_json().encode()) == observed
    result.write(tmp_path / "random")
    assert read_verified_portfolio(tmp_path / "random").model_dump() == result.model_dump()


def test_random_compiles_once_for_the_entire_draw_sequence(monkeypatch):
    import motif_balance.api

    original = motif_balance.api.compile_design
    calls = []

    def counted(spec):
        calls.append(spec)
        return original(spec)

    monkeypatch.setattr(motif_balance.api, "compile_design", counted)
    design(_spec(evaluations=31, count=1), method="random")
    assert len(calls) == 1


@pytest.mark.parametrize("initialization", ["independent", "invalid", None])
def test_random_refuses_irrelevant_initialization_before_compilation(monkeypatch, initialization):
    import motif_balance.api

    monkeypatch.setattr(
        motif_balance.api,
        "compile_design",
        lambda *_: pytest.fail("invalid request reached scoring"),
    )
    with pytest.raises(ValueError, match="initialization"):
        design(_spec(), method="random", initialization=initialization)


def test_random_relabeling_fails_observation_replay():
    _, observation = design_observed(_spec(), ObservationSpec())
    relabeled = observation.model_copy(update={"engine": "uniform_random_v1"})
    with pytest.raises(ValueError, match="replay"):
        read_search_observation(relabeled.model_dump_json().encode())


def test_random_refuses_legacy_before_any_evaluation(monkeypatch):
    import motif_balance.search.uniform
    from motif_balance import DesignSpec
    from motif_balance.errors import IncompatibleDesign

    directional = _spec()
    legacy = DesignSpec(
        motifs=tuple(s.motif for s in directional.specifications),
        length=7,
        count=1,
        evaluations=31,
        seed=7,
    )
    monkeypatch.setattr(
        motif_balance.search.uniform,
        "evaluate",
        lambda *_: pytest.fail("legacy request was evaluated"),
    )
    with pytest.raises(IncompatibleDesign, match="directional"):
        design(legacy, method="random")


@pytest.mark.parametrize("fault", ["impossible_unique_count", "false_exact_status"])
def test_random_bundle_metadata_cannot_invent_coverage(fault):
    from motif_balance.artifacts.verification import verify_portfolio_record
    from motif_balance.errors import ArtifactError

    result = design(_spec(length=2, evaluations=127, count=1), method="random")
    update = (
        {"unique_evaluations": 17}
        if fault == "impossible_unique_count"
        else {"exact_completion_status": "complete"}
    )
    malformed = result.model_copy(update={"manifest": result.manifest.model_copy(update=update)})
    with pytest.raises(ArtifactError, match="coverage"):
        verify_portfolio_record(malformed)
