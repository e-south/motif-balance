from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

import motif_balance
import motif_balance.observation as observation_module
from motif_balance import DesignSpec
from motif_balance.errors import ArtifactError
from motif_balance.observation import (
    MAX_EVALUATED_POOL_RECORDS,
    EvaluatedPoolObservation,
    observe_evaluated_pool,
    read_evaluated_pool,
    verify_evaluated_pool,
    write_evaluated_pool,
)


def test_evaluated_pool_observation_is_complete_bounded_and_not_top_level(
    pairwise_spec: DesignSpec,
) -> None:
    observation = observe_evaluated_pool(pairwise_spec)

    assert observation.schema_version == "evaluated-pool-observation/v2"
    assert observation.evaluation_count == 256
    assert observation.unique_evaluations == 256
    assert len(observation.evaluations) == 256
    assert tuple(item.sequence for item in observation.evaluations) == tuple(
        sorted(item.sequence for item in observation.evaluations)
    )
    assert {item.first_evaluation_index for item in observation.evaluations} == set(range(1, 257))
    assert "observe_evaluated_pool" not in motif_balance.__all__
    with pytest.raises(ValidationError):
        observation.evaluation_count = 1


def test_evaluated_pool_export_is_atomic_path_free_and_refuses_overwrite(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
) -> None:
    observation = observe_evaluated_pool(pairwise_spec)
    output = tmp_path / "pool.json"

    write_evaluated_pool(observation, output)
    payload = json.loads(output.read_text())

    assert payload["observation_id"] == observation.observation_id
    assert read_evaluated_pool(output) == observation
    assert str(tmp_path) not in output.read_text()
    with pytest.raises(ArtifactError, match="already exists"):
        write_evaluated_pool(observation, output)

    link = tmp_path / "link.json"
    link.symlink_to(output)
    with pytest.raises(ArtifactError, match=r"already exists|unsafe"):
        write_evaluated_pool(observation, link)


def test_evaluated_pool_reader_rejects_symlinks_tampering_and_oversized_input(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observation = observe_evaluated_pool(pairwise_spec)
    source = tmp_path / "pool.json"
    write_evaluated_pool(observation, source)

    link = tmp_path / "pool-link.json"
    link.symlink_to(source)
    with pytest.raises(ArtifactError, match="symbolic link"):
        read_evaluated_pool(link)

    payload = json.loads(source.read_text())
    payload["evaluations"][0]["sequence"] = "TTTT"
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    with pytest.raises(ArtifactError, match=r"malformed|identity"):
        read_evaluated_pool(tampered)

    payload = json.loads(source.read_text())
    payload["evaluations"][0]["first_evaluation_index"] = 2
    reordered = tmp_path / "reordered.json"
    reordered.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    with pytest.raises(ArtifactError, match=r"malformed|identity|search replay"):
        read_evaluated_pool(reordered)

    monkeypatch.setattr(observation_module, "MAX_EVALUATED_POOL_BYTES", 16)
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"x" * 17)
    with pytest.raises(ArtifactError, match="byte limit"):
        read_evaluated_pool(oversized)


def test_evaluated_pool_reader_rejects_inode_substitution_before_open(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "pool.json"
    write_evaluated_pool(observe_evaluated_pool(pairwise_spec), source)
    real_open = os.open
    substituted = False

    def substitute_then_open(path: str | os.PathLike[str], flags: int) -> int:
        nonlocal substituted
        if Path(path) == source and not substituted:
            substituted = True
            original = tmp_path / "original.json"
            source.rename(original)
            source.symlink_to(original.name)
        return real_open(path, flags)

    monkeypatch.setattr(observation_module.os, "open", substitute_then_open)

    with pytest.raises(ArtifactError, match=r"unsafe|changed"):
        read_evaluated_pool(source)


def test_evaluated_pool_observation_rejects_work_above_its_explicit_record_limit(
    pairwise_spec: DesignSpec,
) -> None:
    oversized = pairwise_spec.model_copy(
        update={"length": 9, "evaluations": MAX_EVALUATED_POOL_RECORDS + 1}
    )

    with pytest.raises(ArtifactError, match="record limit"):
        observe_evaluated_pool(oversized)


def test_evaluated_pool_writer_replays_science_before_publication(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
) -> None:
    observation = observe_evaluated_pool(pairwise_spec)
    forged = observation.model_copy(update={"problem_id": "problem-" + "0" * 24})

    with pytest.raises(ArtifactError, match="problem identity"):
        write_evaluated_pool(forged, tmp_path / "forged.json")


@pytest.mark.parametrize(
    "update, message",
    [
        ({"unique_evaluations": 1}, "complete observation rows"),
        ({"evaluation_count": 1}, "cannot exceed evaluator calls"),
    ],
)
def test_evaluated_pool_model_rejects_inconsistent_counts(
    pairwise_spec: DesignSpec, update: dict[str, int], message: str
) -> None:
    payload = observe_evaluated_pool(pairwise_spec).model_dump(mode="python")
    payload.update(update)
    with pytest.raises(ValidationError, match=message):
        EvaluatedPoolObservation.model_validate(payload)


def test_evaluated_pool_model_rejects_unsorted_or_duplicate_rows(
    pairwise_spec: DesignSpec,
) -> None:
    observation = observe_evaluated_pool(pairwise_spec)
    payload = observation.model_dump(mode="python")
    payload["evaluations"] = tuple(reversed(payload["evaluations"]))
    with pytest.raises(ValidationError, match="unique and sorted"):
        EvaluatedPoolObservation.model_validate(payload)


def test_evaluated_pool_verifier_rejects_forged_first_evaluation_order(
    pairwise_spec: DesignSpec,
) -> None:
    observation = observe_evaluated_pool(pairwise_spec)
    payload = observation.model_dump(mode="python")
    first = dict(payload["evaluations"][0])
    second = dict(payload["evaluations"][1])
    first["first_evaluation_index"], second["first_evaluation_index"] = (
        second["first_evaluation_index"],
        first["first_evaluation_index"],
    )
    payload["evaluations"] = (first, second, *payload["evaluations"][2:])
    forged = EvaluatedPoolObservation.model_validate(payload)

    with pytest.raises(ArtifactError, match="search replay"):
        verify_evaluated_pool(forged)


def test_evaluated_pool_verifier_rejects_omitted_rows_and_forged_checkpoints(
    pairwise_spec: DesignSpec,
) -> None:
    observation = observe_evaluated_pool(pairwise_spec)
    payload = observation.model_dump(mode="python")
    payload["evaluations"] = payload["evaluations"][:-1]
    payload["unique_evaluations"] -= 1
    with pytest.raises(ValidationError, match="complete sequence-space"):
        EvaluatedPoolObservation.model_validate(payload)

    diagnostic_payload = observation.diagnostics.model_dump(mode="python")
    diagnostic_payload["checkpoints"] = diagnostic_payload["checkpoints"][:-1]
    payload = observation.model_dump(mode="python")
    payload["diagnostics"] = diagnostic_payload
    with pytest.raises(ValidationError, match="final search checkpoint"):
        EvaluatedPoolObservation.model_validate(payload)


@pytest.mark.parametrize(
    "update, message",
    [
        ({"run_id": "run-" + "0" * 24}, "run identity"),
        ({"search_engine": "wrong"}, "run identity"),
        ({"evaluation_count": 255}, "search metadata"),
    ],
)
def test_evaluated_pool_verifier_rejects_forged_contract_metadata(
    pairwise_spec: DesignSpec, update: dict[str, object], message: str
) -> None:
    forged = observe_evaluated_pool(pairwise_spec).model_copy(update=update)
    with pytest.raises(ArtifactError, match=message):
        verify_evaluated_pool(forged)
