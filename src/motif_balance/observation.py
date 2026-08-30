from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from motif_balance.compile import build_run_id, compile_design, sequence_space_at_most
from motif_balance.constants import (
    PACKAGE_VERSION,
    RNG_NAME,
    SEARCH_ENGINE,
    SEARCH_ENGINE_VERSION,
)
from motif_balance.errors import ArtifactError
from motif_balance.model import DesignSpec, Evaluation, FrozenModel, SearchDiagnostics
from motif_balance.scoring import evaluate
from motif_balance.search import SearchResult, search

# Keep the observer bounded to its demonstrated 32,768-call analysis need; the
# independent 64 MiB encoded byte limit still rejects unusually large records
# before publication.
MAX_EVALUATED_POOL_RECORDS = 32_768
MAX_EVALUATED_POOL_BYTES = 64 * 1024 * 1024


def _canonical_payload(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()


class ObservedEvaluation(Evaluation):
    """One unique evaluation with its first authoritative evaluator-call index."""

    first_evaluation_index: Annotated[int, Field(strict=True, gt=0)]


class EvaluatedPoolObservation(FrozenModel):
    """Complete immutable evaluated pool from one bounded search operation."""

    schema_version: Literal["evaluated-pool-observation/v2"] = "evaluated-pool-observation/v2"
    observation_id: str = Field(pattern=r"^pool-[0-9a-f]{24}$")
    package_version: str
    problem_id: str = Field(pattern=r"^problem-[0-9a-f]{24}$")
    run_id: str = Field(pattern=r"^run-[0-9a-f]{24}$")
    spec: DesignSpec
    search_engine: str
    search_engine_version: str
    rng: str
    completion_status: Literal["exhaustive", "budget_exhausted"]
    evaluation_count: Annotated[int, Field(strict=True, gt=0)]
    unique_evaluations: Annotated[int, Field(strict=True, gt=0)]
    diagnostics: SearchDiagnostics
    evaluations: tuple[ObservedEvaluation, ...]

    @model_validator(mode="after")
    def validate_pool(self) -> Self:
        if self.unique_evaluations != len(self.evaluations):
            raise ValueError("unique_evaluations must equal the complete observation rows")
        if self.unique_evaluations > self.evaluation_count:
            raise ValueError("unique_evaluations cannot exceed evaluator calls")
        if self.diagnostics.checkpoints[-1].evaluations != self.evaluation_count:
            raise ValueError("final search checkpoint must equal evaluator calls")
        if self.completion_status == "exhaustive":
            sequence_space = 4**self.spec.length
            if self.evaluation_count != sequence_space or self.unique_evaluations != sequence_space:
                raise ValueError(
                    "exhaustive observations require the complete sequence-space row set"
                )
        sequences = tuple(item.sequence for item in self.evaluations)
        if sequences != tuple(sorted(sequences)) or len(sequences) != len(set(sequences)):
            raise ValueError("evaluated-pool rows must be unique and sorted by sequence")
        if len(self.evaluations) > MAX_EVALUATED_POOL_RECORDS:
            raise ValueError("evaluated-pool observation exceeds its record limit")
        indices = tuple(item.first_evaluation_index for item in self.evaluations)
        if len(indices) != len(set(indices)) or any(
            index > self.evaluation_count for index in indices
        ):
            raise ValueError("first-evaluation indices must be unique evaluator-call positions")
        if self.completion_status == "exhaustive" and set(indices) != set(
            range(1, self.evaluation_count + 1)
        ):
            raise ValueError(
                "exhaustive observations require every evaluator-call position exactly once"
            )
        return self


def _observed_rows(result: SearchResult) -> tuple[ObservedEvaluation, ...]:
    rows = (
        ObservedEvaluation(
            **evaluation.model_dump(mode="python"),
            first_evaluation_index=first_index,
        )
        for evaluation, first_index in zip(
            result.evaluations,
            result.first_evaluation_indices,
            strict=True,
        )
    )
    return tuple(sorted(rows, key=lambda item: item.sequence))


def _observation_payload(observation: EvaluatedPoolObservation) -> dict[str, object]:
    return observation.model_dump(mode="json", exclude={"observation_id"})


def _observation_id(payload: dict[str, object]) -> str:
    return f"pool-{hashlib.sha256(_canonical_payload(payload)).hexdigest()[:24]}"


def observation_bytes(observation: EvaluatedPoolObservation) -> bytes:
    payload = observation.model_dump(mode="json")
    encoded = _canonical_payload(payload)
    if len(encoded) > MAX_EVALUATED_POOL_BYTES:
        raise ArtifactError(
            f"evaluated-pool export exceeds the {MAX_EVALUATED_POOL_BYTES}-byte limit"
        )
    return encoded


def verify_evaluated_pool(observation: EvaluatedPoolObservation) -> None:
    """Replay identities, search metadata, and every immutable evaluation row."""

    problem = compile_design(observation.spec)
    if problem.problem_id != observation.problem_id:
        raise ArtifactError("evaluated-pool problem identity does not match its specification")
    expected_run = build_run_id(
        observation.spec,
        problem.problem_id,
        observation.search_engine,
        observation.search_engine_version,
        package_version=observation.package_version,
    )
    if expected_run != observation.run_id:
        raise ArtifactError("evaluated-pool run identity does not match its search contract")
    sequence_space = sequence_space_at_most(observation.spec.length, observation.spec.evaluations)
    expected_metadata = (
        ("exhaustive_v1", "1", "none", "exhaustive", sequence_space)
        if sequence_space is not None
        else (
            SEARCH_ENGINE,
            SEARCH_ENGINE_VERSION,
            RNG_NAME,
            "budget_exhausted",
            observation.spec.evaluations,
        )
    )
    actual_metadata = (
        observation.search_engine,
        observation.search_engine_version,
        observation.rng,
        observation.completion_status,
        observation.evaluation_count,
    )
    if actual_metadata != expected_metadata:
        raise ArtifactError("evaluated-pool search metadata is inconsistent")
    for row in observation.evaluations:
        authoritative = evaluate(row.sequence, problem)
        recorded = Evaluation.model_validate(
            row.model_dump(mode="python", exclude={"first_evaluation_index"})
        )
        if authoritative != recorded:
            raise ArtifactError("evaluated-pool scientific replay found scoring drift")
    best_feasible = max(
        (row.balance_score for row in observation.evaluations if row.constraint_feasible),
        default=0.0,
    )
    if observation.diagnostics.best_score != best_feasible:
        raise ArtifactError("evaluated-pool diagnostics do not match the feasible pool")
    replay = search(problem)
    if (
        replay.engine != observation.search_engine
        or replay.engine_version != observation.search_engine_version
        or replay.rng != observation.rng
        or replay.completion_status != observation.completion_status
        or replay.evaluations_used != observation.evaluation_count
        or replay.unique_evaluations != observation.unique_evaluations
        or replay.diagnostics != observation.diagnostics
        or _observed_rows(replay) != observation.evaluations
    ):
        raise ArtifactError("evaluated-pool search replay does not match the complete observation")
    if observation.observation_id != _observation_id(_observation_payload(observation)):
        raise ArtifactError("evaluated-pool observation identity does not match its content")


def observe_evaluated_pool(spec: DesignSpec) -> EvaluatedPoolObservation:
    """Run one bounded search and expose its complete unique evaluation pool."""

    if spec.evaluations > MAX_EVALUATED_POOL_RECORDS:
        raise ArtifactError(
            "evaluated-pool observation exceeds its record limit; "
            f"requested={spec.evaluations}, limit={MAX_EVALUATED_POOL_RECORDS}"
        )
    problem = compile_design(spec)
    result = search(problem)
    run_id = build_run_id(
        spec,
        problem.problem_id,
        result.engine,
        result.engine_version,
        package_version=PACKAGE_VERSION,
    )
    payload: dict[str, object] = {
        "schema_version": "evaluated-pool-observation/v2",
        "package_version": PACKAGE_VERSION,
        "problem_id": problem.problem_id,
        "run_id": run_id,
        "spec": spec,
        "search_engine": result.engine,
        "search_engine_version": result.engine_version,
        "rng": result.rng,
        "completion_status": result.completion_status,
        "evaluation_count": result.evaluations_used,
        "unique_evaluations": result.unique_evaluations,
        "diagnostics": result.diagnostics,
        "evaluations": _observed_rows(result),
    }
    identity_payload = EvaluatedPoolObservation.model_validate(
        {**payload, "observation_id": "pool-" + "0" * 24}
    )
    observation = identity_payload.model_copy(
        update={"observation_id": _observation_id(_observation_payload(identity_payload))}
    )
    # The rows and metadata above come directly from this authoritative search
    # result. Publication and independent reads replay the complete search via
    # verify_evaluated_pool; repeating it here would make observe-then-write run
    # the same bounded search three times without crossing a trust boundary.
    return observation


def write_evaluated_pool(observation: EvaluatedPoolObservation, path: str | Path) -> Path:
    """Atomically create one canonical observation file without replacing an existing path."""

    output = Path(path)
    if output.exists() or output.is_symlink():
        raise ArtifactError(f"evaluated-pool output already exists or is unsafe: '{output.name}'")
    verify_evaluated_pool(observation)
    payload = observation_bytes(observation)
    temporary: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(
            prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
        )
        temporary = Path(name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, output, follow_symlinks=False)
    except FileExistsError as exc:
        raise ArtifactError(
            f"evaluated-pool output already exists or is unsafe: '{output.name}'"
        ) from exc
    except OSError as exc:
        raise ArtifactError(f"unable to publish evaluated-pool output '{output.name}'") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return output


def read_evaluated_pool(path: str | Path) -> EvaluatedPoolObservation:
    """Read and identity-check one bounded regular observation file."""

    source = Path(path)
    descriptor: int | None = None
    try:
        before = os.lstat(source)
        if not stat.S_ISREG(before.st_mode):
            raise ArtifactError("evaluated-pool input must be a regular file, not a symbolic link")
        if before.st_size > MAX_EVALUATED_POOL_BYTES:
            raise ArtifactError("evaluated-pool input exceeds its byte limit")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(source, flags)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
            or opened.st_size != before.st_size
        ):
            raise ArtifactError("evaluated-pool input changed before it was opened")
        chunks: list[bytes] = []
        remaining = MAX_EVALUATED_POOL_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
        if (
            (after.st_dev, after.st_ino) != (opened.st_dev, opened.st_ino)
            or after.st_size != opened.st_size
            or len(raw) != opened.st_size
        ):
            raise ArtifactError("evaluated-pool input changed while it was read")
    except ArtifactError:
        raise
    except OSError as exc:
        raise ArtifactError("evaluated-pool input is unsafe or changed while opening") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if len(raw) > MAX_EVALUATED_POOL_BYTES:
        raise ArtifactError("evaluated-pool input exceeds its byte limit")
    try:
        payload = json.loads(raw)
        observation = EvaluatedPoolObservation.model_validate(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ArtifactError("evaluated-pool input is malformed") from exc
    expected = _observation_id(_observation_payload(observation))
    if observation.observation_id != expected or raw != observation_bytes(observation):
        raise ArtifactError("evaluated-pool identity or canonical encoding does not match")
    verify_evaluated_pool(observation)
    return observation
