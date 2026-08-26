from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from motif_balance.artifacts import (
    artifact_records,
    base_artifact_payloads,
    bundle_id,
    candidates_fasta,
    read_portfolio_record,
    write_bundle,
)
from motif_balance.compile import compile_design
from motif_balance.constants import (
    BUILD_LOCK_SHA256,
    MAX_INPUT_BYTES,
    PACKAGE_VERSION,
    RNG_NAME,
    RUNTIME_CONTRACT,
    SEARCH_ENGINE,
    SEARCH_ENGINE_VERSION,
)
from motif_balance.errors import ArtifactError, InvalidDesign, InvalidMotif
from motif_balance.formats import read_motif
from motif_balance.model import (
    Candidate,
    DesignSpec,
    Evaluation,
    MotifMatch,
    MotifModel,
    PortfolioRecord,
    RunManifest,
)
from motif_balance.report import render_report
from motif_balance.scoring import evaluate
from motif_balance.search import search
from motif_balance.selection import candidate_id_for_sequence, select_candidates

__all__ = [
    "Candidate",
    "DesignSpec",
    "Evaluation",
    "MotifMatch",
    "MotifModel",
    "Portfolio",
    "compile_spec",
    "design",
    "load_spec",
    "read_motif",
    "read_portfolio",
    "score",
    "verify_bundle",
]


class Portfolio(PortfolioRecord):
    """Public immutable portfolio with side-effecting convenience operations."""

    def to_fasta(self) -> str:
        return candidates_fasta(self.candidates).decode()

    def write(self, path: str | Path) -> Path:
        _verify_scientific_replay(self)
        return write_bundle(self, Path(path), _bundle_payloads(self.spec, self.candidates))


def _bundle_payloads(
    spec: DesignSpec,
    candidates: tuple[Candidate, ...],
) -> dict[str, bytes]:
    payloads = base_artifact_payloads(spec, candidates)
    payloads["report.html"] = render_report(spec, candidates)
    return payloads


def load_spec(path: str | Path) -> DesignSpec:
    source = Path(path)
    if source.is_symlink():
        raise InvalidDesign(f"Refusing symbolic-link design specification '{source.name}'.")
    try:
        if source.stat().st_size > MAX_INPUT_BYTES:
            raise InvalidDesign(f"Design specification exceeds the {MAX_INPUT_BYTES}-byte limit.")
        raw = source.read_bytes()
        if len(raw) > MAX_INPUT_BYTES:
            raise InvalidDesign(f"Design specification exceeds the {MAX_INPUT_BYTES}-byte limit.")
        payload = yaml.safe_load(raw)
    except (OSError, yaml.YAMLError) as exc:
        raise InvalidDesign(f"Unable to read design specification: {exc}") from exc
    if not isinstance(payload, dict):
        raise InvalidDesign("Design specification must contain one mapping.")
    motifs = payload.get("motifs")
    if not isinstance(motifs, dict):
        raise InvalidDesign("Design specification motifs must be a name-to-model mapping.")
    resolved: dict[str, MotifModel] = {}
    for motif_id, motif_payload in motifs.items():
        if not isinstance(motif_id, str):
            raise InvalidDesign("Motif mapping keys must be strings.")
        if isinstance(motif_payload, str):
            reference = Path(motif_payload)
            if reference.is_absolute() or ".." in reference.parts:
                raise InvalidDesign(
                    f"Motif reference '{motif_payload}' must remain contained in the "
                    "specification directory."
                )
            candidate = source.parent / reference
            cursor = source.parent
            for component in reference.parts:
                cursor /= component
                if cursor.is_symlink():
                    raise InvalidDesign(
                        f"Motif reference '{motif_payload}' traverses a symbolic link."
                    )
            try:
                candidate.resolve(strict=False).relative_to(source.parent.resolve())
            except ValueError as exc:
                raise InvalidDesign(
                    f"Motif reference '{motif_payload}' is not contained in the "
                    "specification directory."
                ) from exc
            try:
                resolved[motif_id] = read_motif(candidate, motif_id=motif_id)
            except InvalidMotif as exc:
                raise InvalidDesign(str(exc), motif_id=motif_id, hint=exc.hint) from exc
        elif isinstance(motif_payload, dict):
            resolved[motif_id] = MotifModel.model_validate(
                {**motif_payload, "motif_id": motif_payload.get("motif_id", motif_id)}
            )
        else:
            raise InvalidDesign(f"Motif '{motif_id}' must be a path or model mapping.")
    payload["motifs"] = resolved
    return DesignSpec.model_validate(payload)


def compile_spec(spec: DesignSpec) -> str:
    return compile_design(spec).problem_id


def _run_id(
    spec: DesignSpec,
    problem_id: str,
    engine: str,
    engine_version: str,
    *,
    package_version: str,
) -> str:
    payload = {
        "problem_id": problem_id,
        "count": spec.count,
        "min_distance": spec.min_distance,
        "evaluations": spec.evaluations,
        "seed": spec.seed,
        "search_engine": engine,
        "search_engine_version": engine_version,
        "package_version": package_version,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return f"run-{digest[:24]}"


def score(sequence: str, spec: DesignSpec) -> Evaluation:
    return evaluate(sequence, compile_design(spec))


def design(spec: DesignSpec) -> Portfolio:
    problem = compile_design(spec)
    result = search(problem)
    candidates = select_candidates(
        result.evaluations,
        count=spec.count,
        min_distance=spec.min_distance,
        evaluations_used=result.evaluations_used,
    )
    run_id = _run_id(
        spec,
        problem.problem_id,
        result.engine,
        result.engine_version,
        package_version=PACKAGE_VERSION,
    )
    payloads = _bundle_payloads(spec, candidates)
    artifacts = artifact_records(payloads)
    provisional_manifest = RunManifest(
        package_version=PACKAGE_VERSION,
        runtime_contract=RUNTIME_CONTRACT,
        build_lock_sha256=BUILD_LOCK_SHA256,
        problem_id=problem.problem_id,
        run_id=run_id,
        bundle_id="bundle-000000000000000000000000",
        search_engine=result.engine,
        search_engine_version=result.engine_version,
        rng=result.rng,
        evaluation_count=result.evaluations_used,
        unique_evaluations=result.unique_evaluations,
        completion_status=result.completion_status,
        optimizer_parity_status=result.optimizer_parity_status,
        artifacts=artifacts,
    )
    manifest = provisional_manifest.model_copy(
        update={"bundle_id": bundle_id(provisional_manifest)}
    )
    return Portfolio(
        problem_id=problem.problem_id,
        run_id=run_id,
        spec=spec,
        candidates=candidates,
        manifest=manifest,
    )


def _verify_scientific_replay(portfolio: Portfolio) -> None:
    if (
        portfolio.manifest.package_version != PACKAGE_VERSION
        or portfolio.manifest.runtime_contract != RUNTIME_CONTRACT
        or portfolio.manifest.build_lock_sha256 != BUILD_LOCK_SHA256
    ):
        raise ArtifactError("scientific replay found inconsistent package provenance")
    problem = compile_design(portfolio.spec)
    if problem.problem_id != portfolio.manifest.problem_id:
        raise ArtifactError("scientific replay found a problem identity mismatch")
    expected_run = _run_id(
        portfolio.spec,
        problem.problem_id,
        portfolio.manifest.search_engine,
        portfolio.manifest.search_engine_version,
        package_version=portfolio.manifest.package_version,
    )
    if expected_run != portfolio.manifest.run_id:
        raise ArtifactError("scientific replay found a run identity mismatch")

    sequence_space = 4**portfolio.spec.length
    if sequence_space <= portfolio.spec.evaluations:
        expected_metadata = (
            "exhaustive_v1",
            SEARCH_ENGINE_VERSION,
            "none",
            "exhaustive",
            "not_applicable",
            sequence_space,
        )
    else:
        expected_metadata = (
            SEARCH_ENGINE,
            SEARCH_ENGINE_VERSION,
            RNG_NAME,
            "budget_exhausted",
            "not_established",
            portfolio.spec.evaluations,
        )
    actual_metadata = (
        portfolio.manifest.search_engine,
        portfolio.manifest.search_engine_version,
        portfolio.manifest.rng,
        portfolio.manifest.completion_status,
        portfolio.manifest.optimizer_parity_status,
        portfolio.manifest.evaluation_count,
    )
    if actual_metadata != expected_metadata:
        raise ArtifactError("scientific replay found inconsistent search provenance")
    if portfolio.manifest.unique_evaluations > portfolio.manifest.evaluation_count:
        raise ArtifactError("scientific replay found impossible evaluation counts")

    for candidate in portfolio.candidates:
        authoritative = evaluate(candidate.sequence, problem)
        if candidate.candidate_id != candidate_id_for_sequence(candidate.sequence):
            raise ArtifactError(
                f"scientific replay found a candidate identity mismatch for rank {candidate.rank}"
            )
        if (
            candidate.balance_score != authoritative.balance_score
            or candidate.matches != authoritative.matches
        ):
            raise ArtifactError(
                f"scientific replay found scoring drift for '{candidate.candidate_id}'"
            )


def read_portfolio(
    directory: str | Path,
    *,
    expected_bundle_id: str | None = None,
) -> Portfolio:
    root = Path(directory)
    record = read_portfolio_record(root)
    portfolio = Portfolio.model_validate(record.model_dump(mode="python"))
    if expected_bundle_id is not None and portfolio.manifest.bundle_id != expected_bundle_id:
        raise ArtifactError("bundle identity does not match the externally expected identity")
    for path, expected in _bundle_payloads(portfolio.spec, portfolio.candidates).items():
        try:
            actual = (root / path).read_bytes()
        except OSError as exc:
            raise ArtifactError(f"Unable to read bundle artifact '{path}': {exc}") from exc
        if actual != expected:
            raise ArtifactError(f"artifact semantic replay mismatch for '{path}'")
    _verify_scientific_replay(portfolio)
    return portfolio


def verify_bundle(
    directory: str | Path,
    *,
    expected_bundle_id: str | None = None,
) -> str:
    return read_portfolio(
        directory,
        expected_bundle_id=expected_bundle_id,
    ).manifest.bundle_id
