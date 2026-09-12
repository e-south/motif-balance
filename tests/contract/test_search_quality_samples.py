"""Quality-threshold retention is passive, bounded, and not elite ranking."""

from __future__ import annotations

import hashlib
import itertools

import pytest

from motif_balance import DesignSpec, MotifModel, MotifSpecification, design, score
from motif_balance.api import design_observed, verify_search_observation
from motif_balance.model.search_observation import ObservationSpec, SearchObservation


def _request(*, length: int = 2, evaluations: int = 16) -> DesignSpec:
    return DesignSpec(
        schema_version="design-spec/v3",
        specifications=tuple(
            MotifSpecification(
                motif=MotifModel(
                    motif_id=name,
                    probabilities=(probabilities,),
                    background=(0.25, 0.25, 0.25, 0.25),
                ),
                direction="seek",
            )
            for name, probabilities in (
                ("synthetic_a", (0.7, 0.1, 0.1, 0.1)),
                ("synthetic_c", (0.1, 0.7, 0.1, 0.1)),
            )
        ),
        length=length,
        evaluations=evaluations,
        count=1,
        strands="forward",
        seed=19,
    )


def test_exact_quality_samples_include_all_qualifying_sequences_without_changing_design() -> None:
    spec = _request()
    portfolio, observed = design_observed(
        spec,
        ObservationSpec(quality_thresholds=(0.0, 0.5, 1.0), max_sequences_per_threshold=32),
    )
    assert portfolio == design(spec)
    assert observed.schema_version == "search-observation/v2"
    assert [row.threshold for row in observed.quality_samples] == [0.0, 0.5, 1.0]
    low, middle, high = observed.quality_samples
    assert low.qualifying_evaluations == low.unique_sequences == 16
    assert {item.sequence for item in low.evaluations} == {
        "".join(word) for word in itertools.product("ACGT", repeat=2)
    }
    for sample in (middle, high):
        assert sample.qualifying_evaluations == sample.unique_sequences == 2
        assert {item.sequence for item in sample.evaluations} == {"AC", "CA"}
    for sample in observed.quality_samples:
        assert all(item == score(item.sequence, spec) for item in sample.evaluations)
    verify_search_observation(observed)


def test_capacity_uses_sequence_hash_priority_not_score_or_visit_frequency() -> None:
    spec = _request(length=7, evaluations=127)
    _, complete = design_observed(
        spec, ObservationSpec(quality_thresholds=(0.0,), max_sequences_per_threshold=256)
    )
    _, bounded = design_observed(
        spec, ObservationSpec(quality_thresholds=(0.0,), max_sequences_per_threshold=3)
    )
    full, small = complete.quality_samples[0], bounded.quality_samples[0]
    assert full.qualifying_evaluations == small.qualifying_evaluations == 127
    assert len(full.evaluations) == full.unique_sequences == small.unique_sequences < 127
    expected = sorted(
        full.evaluations,
        key=lambda row: (hashlib.sha256(row.sequence.encode()).hexdigest(), row.sequence),
    )[:3]
    assert tuple(expected) == small.evaluations
    assert bounded.snapshots == complete.snapshots
    assert bounded.moves == complete.moves
    assert bounded.target_hits == complete.target_hits


def test_empty_quality_sample_is_explicit() -> None:
    _, observed = design_observed(
        _request(length=1, evaluations=4), ObservationSpec(quality_thresholds=(1.0,))
    )
    sample = observed.quality_samples[0]
    assert sample.qualifying_evaluations == sample.unique_sequences == 0
    assert sample.evaluations == ()


@pytest.mark.parametrize(
    "fields",
    [
        {"quality_thresholds": (0.8, 0.5)},
        {"quality_thresholds": (0.5, 0.5)},
        {"quality_thresholds": (-0.1,)},
        {"quality_thresholds": tuple(index / 20 for index in range(17))},
        {"max_sequences_per_threshold": 0},
        {"max_sequences_per_threshold": 257},
    ],
)
def test_invalid_quality_sample_policy_is_refused(fields) -> None:
    with pytest.raises(ValueError):
        ObservationSpec.model_validate(fields)


@pytest.mark.parametrize(
    "corruption", ["missing", "count", "threshold", "duplicate", "capacity", "version"]
)
def test_quality_sample_contract_fails_closed(corruption) -> None:
    _, observed = design_observed(
        _request(), ObservationSpec(quality_thresholds=(0.0,), max_sequences_per_threshold=2)
    )
    payload = observed.model_dump(mode="python")
    if corruption == "missing":
        del payload["quality_samples"]
    elif corruption == "count":
        payload["quality_samples"][0]["unique_sequences"] = 100
    elif corruption == "threshold":
        payload["quality_samples"][0]["threshold"] = 0.5
    elif corruption == "duplicate":
        row = payload["quality_samples"][0]["evaluations"][0]
        payload["quality_samples"][0]["evaluations"] = (row, row)
    elif corruption == "capacity":
        payload["observation_spec"]["max_sequences_per_threshold"] = 1
    else:
        payload["schema_version"] = "search-observation/v1"
    with pytest.raises(ValueError):
        SearchObservation.model_validate(payload)


def test_fabricated_quality_membership_is_caught_by_replay() -> None:
    _, observed = design_observed(_request(), ObservationSpec(quality_thresholds=(0.0,)))
    payload = observed.model_dump(mode="python")
    payload["quality_samples"][0]["qualifying_evaluations"] -= 1
    payload["quality_samples"][0]["unique_sequences"] -= 1
    payload["quality_samples"][0]["evaluations"] = payload["quality_samples"][0]["evaluations"][:-1]
    corrupted = SearchObservation.model_validate(payload)
    with pytest.raises(ValueError, match="replay"):
        verify_search_observation(corrupted)


def test_observation_revalidates_unchecked_config_before_search(monkeypatch) -> None:
    from motif_balance.search import AnnealedSearchEngine

    def forbidden(*args, **kwargs):
        pytest.fail("invalid observation policy reached search")

    monkeypatch.setattr(AnnealedSearchEngine, "search", forbidden)
    unchecked = ObservationSpec().model_copy(update={"max_snapshots": 0})
    with pytest.raises(ValueError):
        design_observed(_request(), unchecked)


def test_observation_byte_projection_accounts_for_repeated_identifiers(monkeypatch) -> None:
    from motif_balance.search import AnnealedSearchEngine

    payload = _request().model_dump(mode="python")
    for index, item in enumerate(payload["specifications"]):
        item["motif"]["motif_id"] = "m" + str(index) + "a" * 100_000
    spec = DesignSpec.model_validate(payload)

    def forbidden(*args, **kwargs):
        pytest.fail("oversized observation reached search")

    monkeypatch.setattr(AnnealedSearchEngine, "search", forbidden)
    with pytest.raises(ValueError, match="byte limit"):
        design_observed(spec, ObservationSpec(max_snapshots=256))
