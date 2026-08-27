from __future__ import annotations

import hashlib
import math
from html import escape
from itertools import islice
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from motif_balance.constants import MAX_BUNDLE_ARTIFACT_BYTES, MAX_DISTANCE_BASE_COMPARISONS
from motif_balance.errors import ArtifactError
from motif_balance.model import (
    ArtifactDigest,
    Candidate,
    ExecutionDependency,
    ExecutionReceipt,
    ExecutionWorkspace,
    FrozenModel,
    MotifConversion,
    PortfolioRecord,
    SearchDiagnostics,
)
from motif_balance.visualization import (
    render_candidate_match_map,
    render_portfolio_balance_profile,
    render_search_progress,
)

_MAX_CATALOG_ENTRIES = 100
_MAX_HTML_CANDIDATES = 500
_MAX_HTML_MATCHES = 1_000
_MAX_HTML_CHECKPOINTS = 500

_CLAIM_SCOPE = (
    "Computational scores are meaningful only under the declared motif models and semantics.",
    "Budget exhaustion does not establish global optimality.",
    "Within-run diagnostics are not comparative evidence or biological replicates.",
    "The result does not establish binding, occupancy, expression, or regulatory function.",
)


class InspectionMotif(FrozenModel):
    motif_id: str
    width: Annotated[int, Field(gt=0)]
    model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_name: str | None = None
    source_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    canonical_file_name: str | None = None
    canonical_file_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    conversion: MotifConversion | None = None


class InspectionProblem(FrozenModel):
    problem_id: str = Field(pattern=r"^problem-[0-9a-f]{24}$")
    motifs: tuple[InspectionMotif, ...]
    length: Annotated[int, Field(gt=0)]
    strands: Literal["forward", "both"]
    scoring_semantics: str
    objective_semantics: str
    tie_break_semantics: str


class InspectionRun(FrozenModel):
    run_id: str = Field(pattern=r"^run-[0-9a-f]{24}$")
    bundle_id: str = Field(pattern=r"^bundle-[0-9a-f]{24}$")
    package_version: str
    runtime_contract: str
    build_lock_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    requested_count: Annotated[int, Field(gt=0)]
    seed: Annotated[int, Field(ge=0)]
    evaluations_requested: Annotated[int, Field(gt=0)]
    min_distance_requested: Annotated[float, Field(ge=0.0, le=1.0)] | None
    search_engine: str
    search_engine_version: str
    rng: str
    completion_status: Literal["exhaustive", "budget_exhausted"]
    evaluation_count: Annotated[int, Field(gt=0)]
    unique_evaluations: Annotated[int, Field(gt=0)]
    search_validation_status: Literal["not_applicable", "contract_tested"]


class LimitingMotifCount(FrozenModel):
    motif_id: str
    candidates: Annotated[int, Field(gt=0)]


class DistanceInspection(FrozenModel):
    status: Literal["exact", "not_applicable", "not_computed_limit"]
    actual_min_distance: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    closest_candidate_ids: tuple[str, str] | None = None
    base_comparisons: Annotated[int, Field(ge=0)]
    computation_limit: Literal[10_000_000] = 10_000_000

    @model_validator(mode="after")
    def validate_state(self) -> DistanceInspection:
        has_result = self.actual_min_distance is not None or self.closest_candidate_ids is not None
        if self.status == "exact" and (
            self.actual_min_distance is None or self.closest_candidate_ids is None
        ):
            raise ValueError("exact distance inspection requires a value and candidate pair")
        if self.status != "exact" and has_result:
            raise ValueError("non-exact distance inspection cannot report an exact result")
        if self.status == "not_computed_limit" and self.base_comparisons <= self.computation_limit:
            raise ValueError("distance limit state requires work above the declared limit")
        return self


class InspectionPortfolio(FrozenModel):
    returned_count: Annotated[int, Field(gt=0)]
    score_min: Annotated[float, Field(ge=0.0)]
    score_max: Annotated[float, Field(ge=0.0)]
    distance: DistanceInspection
    limiting_motifs: tuple[LimitingMotifCount, ...]
    candidates: tuple[Candidate, ...]

    @model_validator(mode="after")
    def validate_summary(self) -> InspectionPortfolio:
        if self.returned_count != len(self.candidates):
            raise ValueError("returned_count must equal the number of candidates")
        scores = [candidate.balance_score for candidate in self.candidates]
        if not math.isclose(self.score_min, min(scores), abs_tol=1.0e-12):
            raise ValueError("score_min does not match the candidate portfolio")
        if not math.isclose(self.score_max, max(scores), abs_tol=1.0e-12):
            raise ValueError("score_max does not match the candidate portfolio")
        return self


class InspectionArtifact(FrozenModel):
    key: str
    role: Literal["canonical", "derived"]
    path: str
    format: str
    bytes: Annotated[int, Field(ge=0)]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ResultIndex(FrozenModel):
    schema_version: Literal["motif-balance.result-index/v1"] = "motif-balance.result-index/v1"
    problem: InspectionProblem
    run: InspectionRun
    portfolio: InspectionPortfolio
    diagnostics: SearchDiagnostics
    artifacts: tuple[InspectionArtifact, ...]
    claim_scope: tuple[str, ...] = _CLAIM_SCOPE

    @model_validator(mode="after")
    def validate_artifacts(self) -> ResultIndex:
        paths = [artifact.path for artifact in self.artifacts]
        if paths != sorted(paths) or len(paths) != len(set(paths)):
            raise ValueError("inspection artifacts must be unique and sorted by path")
        return self


class ExecutionInspection(FrozenModel):
    workspace_id: str = Field(pattern=r"^execution-[0-9a-f]{24}$")
    producer_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    release_artifact_name: str
    release_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_package_tree_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    started_at_utc: str
    finished_at_utc: str
    duration_seconds: Annotated[float, Field(ge=0.0)]
    python_version: str
    platform_system: str
    platform_machine: str
    dependencies: tuple[ExecutionDependency, ...]


class ResultInspection(FrozenModel):
    schema_version: Literal["motif-balance.result-inspection/v1"] = (
        "motif-balance.result-inspection/v1"
    )
    subject_kind: Literal["bundle", "execution"]
    integrity_status: Literal["verified", "readable_untrusted"]
    trust_basis: Literal[
        "self_consistent",
        "external_bundle_id",
        "external_execution_identities",
    ]
    trusted_identities_checked: tuple[str, ...]
    result: ResultIndex
    execution: ExecutionInspection | None = None

    @model_validator(mode="after")
    def validate_kind(self) -> ResultInspection:
        if self.subject_kind == "execution" and self.execution is None:
            raise ValueError("execution inspection requires execution provenance")
        if self.subject_kind == "bundle" and self.execution is not None:
            raise ValueError("bundle inspection cannot contain execution provenance")
        if self.subject_kind == "bundle":
            bundle_checked = ("bundle_id",) if self.trust_basis == "external_bundle_id" else ()
            if (
                self.integrity_status != "verified"
                or self.trust_basis not in {"self_consistent", "external_bundle_id"}
                or self.trusted_identities_checked != bundle_checked
            ):
                raise ValueError("bundle inspection trust fields are inconsistent")
        if self.subject_kind == "execution":
            external = self.trust_basis == "external_execution_identities"
            execution_checked = (
                ("workspace_id", "receipt_sha256", "release_sha256", "producer_revision")
                if external
                else ()
            )
            expected_integrity = "verified" if external else "readable_untrusted"
            if (
                self.trust_basis not in {"self_consistent", "external_execution_identities"}
                or self.integrity_status != expected_integrity
                or self.trusted_identities_checked != execution_checked
            ):
                raise ValueError("execution inspection trust fields are inconsistent")
        return self


class CatalogEntry(FrozenModel):
    entry_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    subject_kind: Literal["bundle", "execution"]
    integrity_status: Literal["verified", "readable_untrusted"]
    trust_basis: Literal[
        "self_consistent",
        "external_bundle_id",
        "external_execution_identities",
    ]
    problem_id: str = Field(pattern=r"^problem-[0-9a-f]{24}$")
    run_id: str = Field(pattern=r"^run-[0-9a-f]{24}$")
    bundle_id: str = Field(pattern=r"^bundle-[0-9a-f]{24}$")
    workspace_id: str | None = Field(default=None, pattern=r"^execution-[0-9a-f]{24}$")
    motif_ids: tuple[str, ...]
    length: Annotated[int, Field(gt=0)]
    returned_count: Annotated[int, Field(gt=0)]
    score_min: Annotated[float, Field(ge=0.0)]
    score_max: Annotated[float, Field(ge=0.0)]
    distance_status: Literal["exact", "not_applicable", "not_computed_limit"]
    completion_status: Literal["exhaustive", "budget_exhausted"]
    package_version: str
    scoring_semantics: str
    objective_semantics: str
    tie_break_semantics: str

    @model_validator(mode="after")
    def validate_summary(self) -> CatalogEntry:
        if (self.subject_kind == "execution") != (self.workspace_id is not None):
            raise ValueError("catalog execution entries require a workspace identity")
        if self.score_min > self.score_max:
            raise ValueError("catalog score range is inverted")
        if not self.motif_ids or len(self.motif_ids) != len(set(self.motif_ids)):
            raise ValueError("catalog motif identifiers must be nonempty and unique")
        return self


class ResultCatalog(FrozenModel):
    schema_version: Literal["motif-balance.result-catalog/v1"] = "motif-balance.result-catalog/v1"
    entries: tuple[CatalogEntry, ...]

    @model_validator(mode="after")
    def validate_entries(self) -> ResultCatalog:
        ids = [entry.entry_id for entry in self.entries]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError("catalog entry identifiers must be unique and sorted")
        if not ids or len(ids) > _MAX_CATALOG_ENTRIES:
            raise ValueError(f"catalog must contain 1..{_MAX_CATALOG_ENTRIES} entries")
        return self


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _artifact(
    *,
    key: str,
    role: Literal["canonical", "derived"],
    path: str,
    payload: bytes,
) -> InspectionArtifact:
    return InspectionArtifact(
        key=key,
        role=role,
        path=path,
        format=Path(path).suffix.removeprefix(".") or "directory",
        bytes=len(payload),
        sha256=_digest(payload),
    )


def _distance_inspection(candidates: tuple[Candidate, ...]) -> DistanceInspection:
    if len(candidates) < 2:
        return DistanceInspection(status="not_applicable", base_comparisons=0)
    sequence_length = len(candidates[0].sequence)
    pair_count = len(candidates) * (len(candidates) - 1) // 2
    base_comparisons = pair_count * sequence_length
    if base_comparisons > MAX_DISTANCE_BASE_COMPARISONS:
        return DistanceInspection(
            status="not_computed_limit",
            base_comparisons=base_comparisons,
        )
    closest_distance = math.inf
    closest_ids: tuple[str, str] | None = None
    for index, left in enumerate(candidates):
        for right in candidates[index + 1 :]:
            distance = (
                sum(a != b for a, b in zip(left.sequence, right.sequence, strict=True))
                / sequence_length
            )
            if distance < closest_distance:
                closest_distance = distance
                closest_ids = (left.candidate_id, right.candidate_id)
    assert closest_ids is not None
    return DistanceInspection(
        status="exact",
        actual_min_distance=closest_distance,
        closest_candidate_ids=closest_ids,
        base_comparisons=base_comparisons,
    )


def _read_current_artifact(root: Path, record: ArtifactDigest) -> bytes:
    """Read one declared current artifact and bind the projection to verified bytes."""

    relative = Path(record.path)
    if (
        relative.is_absolute()
        or len(relative.parts) != 1
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise ArtifactError("bundle inspection encountered an unsafe artifact path")
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise ArtifactError(f"bundle inspection encountered unsafe artifact '{record.path}'")
    if record.bytes > MAX_BUNDLE_ARTIFACT_BYTES:
        raise ArtifactError(f"bundle artifact '{record.path}' exceeds the byte limit")
    try:
        if path.stat().st_size != record.bytes:
            raise ArtifactError(f"bundle artifact '{record.path}' changed during inspection")
        payload = path.read_bytes()
    except OSError as exc:
        raise ArtifactError(f"unable to read bundle artifact '{record.path}'") from exc
    if len(payload) != record.bytes or _digest(payload) != record.sha256:
        raise ArtifactError(f"bundle artifact '{record.path}' changed during inspection")
    return payload


def build_result_index(
    root: Path,
    portfolio: PortfolioRecord,
    *,
    canonical_manifest: bytes,
) -> ResultIndex:
    limiting: dict[str, int] = {}
    for candidate in portfolio.candidates:
        weakest = candidate.balance_score
        for match in candidate.matches:
            if math.isclose(match.normalized_score, weakest, abs_tol=1.0e-12):
                limiting[match.motif_id] = limiting.get(match.motif_id, 0) + 1

    artifacts = []
    for record in portfolio.manifest.artifacts:
        payload = _read_current_artifact(root, record)
        role: Literal["canonical", "derived"] = (
            "derived" if record.path in {"candidates.fasta", "report.html"} else "canonical"
        )
        artifacts.append(
            _artifact(
                key=record.path.replace(".", "_"), role=role, path=record.path, payload=payload
            )
        )
    manifest_payload = _read_current_artifact(
        root,
        ArtifactDigest(
            path="manifest.json",
            bytes=len(canonical_manifest),
            sha256=_digest(canonical_manifest),
        ),
    )
    artifacts.append(
        _artifact(
            key="manifest_json",
            role="canonical",
            path="manifest.json",
            payload=manifest_payload,
        )
    )
    spec = portfolio.spec
    manifest = portfolio.manifest
    return ResultIndex(
        problem=InspectionProblem(
            problem_id=portfolio.problem_id,
            motifs=tuple(
                InspectionMotif(
                    motif_id=motif.motif_id,
                    width=motif.width,
                    model_digest=motif.model_digest,
                    source_name=motif.source_name,
                    source_digest=motif.source_digest,
                    canonical_file_name=motif.canonical_file_name,
                    canonical_file_digest=motif.canonical_file_digest,
                    conversion=motif.conversion,
                )
                for motif in spec.motifs
            ),
            length=spec.length,
            strands=spec.strands,
            scoring_semantics=spec.scoring_semantics,
            objective_semantics=spec.objective_semantics,
            tie_break_semantics=spec.tie_break_semantics,
        ),
        run=InspectionRun(
            run_id=portfolio.run_id,
            bundle_id=manifest.bundle_id,
            package_version=manifest.package_version,
            runtime_contract=manifest.runtime_contract,
            build_lock_sha256=manifest.build_lock_sha256,
            requested_count=spec.count,
            seed=spec.seed,
            evaluations_requested=spec.evaluations,
            min_distance_requested=spec.min_distance,
            search_engine=manifest.search_engine,
            search_engine_version=manifest.search_engine_version,
            rng=manifest.rng,
            completion_status=manifest.completion_status,
            evaluation_count=manifest.evaluation_count,
            unique_evaluations=manifest.unique_evaluations,
            search_validation_status=manifest.search_validation_status,
        ),
        portfolio=InspectionPortfolio(
            returned_count=len(portfolio.candidates),
            score_min=min(candidate.balance_score for candidate in portfolio.candidates),
            score_max=max(candidate.balance_score for candidate in portfolio.candidates),
            distance=_distance_inspection(portfolio.candidates),
            limiting_motifs=tuple(
                LimitingMotifCount(motif_id=motif_id, candidates=count)
                for motif_id, count in sorted(limiting.items())
            ),
            candidates=portfolio.candidates,
        ),
        diagnostics=manifest.search_diagnostics,
        artifacts=tuple(sorted(artifacts, key=lambda item: item.path)),
    )


def build_execution_inspection(
    workspace: ExecutionWorkspace,
    receipt: ExecutionReceipt,
) -> ExecutionInspection:
    from datetime import datetime

    started = datetime.strptime(receipt.started_at_utc, "%Y-%m-%dT%H:%M:%SZ")
    finished = datetime.strptime(receipt.finished_at_utc, "%Y-%m-%dT%H:%M:%SZ")
    return ExecutionInspection(
        workspace_id=workspace.workspace_id,
        producer_revision=receipt.producer_revision,
        release_artifact_name=receipt.release_artifact_name,
        release_artifact_sha256=receipt.release_artifact_sha256,
        runtime_package_tree_sha256=receipt.runtime_package_tree_sha256,
        receipt_sha256=workspace.receipt.sha256,
        manifest_sha256=receipt.manifest_sha256,
        started_at_utc=receipt.started_at_utc,
        finished_at_utc=receipt.finished_at_utc,
        duration_seconds=(finished - started).total_seconds(),
        python_version=receipt.python_version,
        platform_system=receipt.platform_system,
        platform_machine=receipt.platform_machine,
        dependencies=receipt.dependencies,
    )


def catalog(entries: dict[str, ResultInspection]) -> ResultCatalog:
    return ResultCatalog(
        entries=tuple(
            CatalogEntry(
                entry_id=entry_id,
                subject_kind=inspection.subject_kind,
                integrity_status=inspection.integrity_status,
                trust_basis=inspection.trust_basis,
                problem_id=inspection.result.problem.problem_id,
                run_id=inspection.result.run.run_id,
                bundle_id=inspection.result.run.bundle_id,
                workspace_id=(
                    inspection.execution.workspace_id if inspection.execution is not None else None
                ),
                motif_ids=tuple(motif.motif_id for motif in inspection.result.problem.motifs),
                length=inspection.result.problem.length,
                returned_count=inspection.result.portfolio.returned_count,
                score_min=inspection.result.portfolio.score_min,
                score_max=inspection.result.portfolio.score_max,
                distance_status=inspection.result.portfolio.distance.status,
                completion_status=inspection.result.run.completion_status,
                package_version=inspection.result.run.package_version,
                scoring_semantics=inspection.result.problem.scoring_semantics,
                objective_semantics=inspection.result.problem.objective_semantics,
                tie_break_semantics=inspection.result.problem.tie_break_semantics,
            )
            for entry_id, inspection in sorted(entries.items())
        )
    )


def inspection_text(inspection: ResultInspection) -> str:
    """Render a compact terminal summary without source filesystem paths."""

    result = inspection.result
    distance = result.portfolio.distance
    lines = [
        f"kind={inspection.subject_kind}",
        f"integrity={inspection.integrity_status}",
        f"trust={inspection.trust_basis}",
        f"problem_id={result.problem.problem_id}",
        f"run_id={result.run.run_id}",
        f"bundle_id={result.run.bundle_id}",
        f"motifs={','.join(motif.motif_id for motif in result.problem.motifs)}",
        f"length={result.problem.length}",
        f"requested_count={result.run.requested_count}",
        f"returned_count={result.portfolio.returned_count}",
        f"score_range={result.portfolio.score_min:.17g}..{result.portfolio.score_max:.17g}",
        f"distance_status={distance.status}",
        f"actual_min_distance={distance.actual_min_distance}",
        f"completion={result.run.completion_status}",
        f"evaluations={result.run.evaluation_count}",
        f"unique_evaluations={result.run.unique_evaluations}",
    ]
    if inspection.execution is not None:
        lines.extend(
            (
                f"workspace_id={inspection.execution.workspace_id}",
                f"release_sha256={inspection.execution.release_artifact_sha256}",
                f"producer_revision={inspection.execution.producer_revision}",
            )
        )
    return "\n".join(lines) + "\n"


def _html_rows(rows: list[tuple[str, object]]) -> str:
    return "\n".join(
        f'<tr><th scope="row">{escape(label)}</th><td><code>{escape(str(value))}</code></td></tr>'
        for label, value in rows
    )


def _limiting_ids(candidate: Candidate) -> str:
    return ", ".join(
        match.motif_id
        for match in candidate.matches
        if math.isclose(
            match.normalized_score,
            candidate.balance_score,
            abs_tol=1.0e-12,
        )
    )


def _details(label: str, contents: str) -> str:
    return (
        f'<details><summary>{escape(label)}</summary><div class="detail">{contents}</div></details>'
    )


def inspection_html(inspection: ResultInspection) -> bytes:
    """Render a self-contained, script-free review view."""

    result = inspection.result
    distance = result.portfolio.distance
    distance_value = (
        format(distance.actual_min_distance, ".17g")
        if distance.actual_min_distance is not None
        else "not computed"
    )
    start_rows = _html_rows(
        [
            ("Problem", result.problem.problem_id),
            ("Run", result.run.run_id),
            ("Bundle", result.run.bundle_id),
            ("Motifs", ", ".join(motif.motif_id for motif in result.problem.motifs)),
            ("Length", result.problem.length),
            ("Requested candidates", result.run.requested_count),
            ("Returned candidates", result.portfolio.returned_count),
            (
                "Score range",
                f"{result.portfolio.score_min:.17g} .. {result.portfolio.score_max:.17g}",
            ),
            ("Distance status", distance.status),
            ("Actual minimum distance", distance_value),
            ("Completion", result.run.completion_status),
        ]
    )
    shown_candidates = result.portfolio.candidates[:_MAX_HTML_CANDIDATES]
    candidate_rows = "\n".join(
        "<tr>"
        f"<td>{candidate.rank}</td><td><code>{escape(candidate.candidate_id)}</code></td>"
        f'<td><code class="sequence">{escape(candidate.sequence)}</code></td>'
        f"<td>{candidate.balance_score:.17g}</td>"
        f"<td>{escape(_limiting_ids(candidate))}</td></tr>"
        for candidate in shown_candidates
    )
    candidate_limit = (
        f"<p>Showing {_MAX_HTML_CANDIDATES} of {result.portfolio.returned_count} candidates. "
        "Use the verified TSV or JSON projection for the complete set.</p>"
        if result.portfolio.returned_count > _MAX_HTML_CANDIDATES
        else ""
    )
    motif_rows = "\n".join(
        "<tr>"
        f"<td>{escape(motif.motif_id)}</td><td>{motif.width}</td>"
        f"<td><code>{motif.model_digest}</code></td>"
        f"<td>{escape(str(motif.source_name or ''))}</td>"
        f"<td><code>{escape(str(motif.source_digest or ''))}</code></td>"
        f"<td>{escape(str(motif.canonical_file_name or ''))}</td>"
        f"<td><code>{escape(str(motif.canonical_file_digest or ''))}</code></td>"
        f"<td>{escape(motif.conversion.method if motif.conversion else '')}</td>"
        f"<td>{motif.conversion.prior_weight if motif.conversion else ''}</td></tr>"
        for motif in result.problem.motifs
    )
    match_count = sum(len(candidate.matches) for candidate in result.portfolio.candidates)
    shown_matches = islice(
        (
            (candidate, match)
            for candidate in result.portfolio.candidates
            for match in candidate.matches
        ),
        _MAX_HTML_MATCHES,
    )
    match_rows = "\n".join(
        "<tr>"
        f"<td>{candidate.rank}</td><td>{escape(match.motif_id)}</td>"
        f"<td>{match.start}</td><td>{match.end}</td><td>{match.strand}</td>"
        f"<td><code>{escape(match.matched_sequence)}</code></td>"
        f"<td>{match.raw_score:.17g}</td><td>{match.normalized_score:.17g}</td></tr>"
        for candidate, match in shown_matches
    )
    match_limit = (
        f"<p>Showing {_MAX_HTML_MATCHES} of {match_count} matches. "
        "Use matches.tsv or the JSON projection for the complete set.</p>"
        if match_count > _MAX_HTML_MATCHES
        else ""
    )
    shown_checkpoints = result.diagnostics.checkpoints[:_MAX_HTML_CHECKPOINTS]
    checkpoint_rows = "\n".join(
        f"<tr><td>{item.evaluations}</td><td>{item.best_score:.17g}</td></tr>"
        for item in shown_checkpoints
    )
    checkpoint_limit = (
        f"<p>Showing {_MAX_HTML_CHECKPOINTS} of "
        f"{len(result.diagnostics.checkpoints)} checkpoints. "
        "Use the JSON projection for the complete set.</p>"
        if len(result.diagnostics.checkpoints) > _MAX_HTML_CHECKPOINTS
        else ""
    )
    proposal_rows = "\n".join(
        f"<tr><td>{escape(item.move)}</td><td>{item.attempted}</td><td>{item.accepted}</td>"
        f"<td>{(item.accepted / item.attempted if item.attempted else 0):.6f}</td></tr>"
        for item in result.diagnostics.proposals
    )
    artifact_rows = "\n".join(
        "<tr>"
        f"<td>{escape(item.key)}</td><td>{escape(item.role)}</td><td>{escape(item.format)}</td>"
        f"<td><code>{escape(item.path)}</code></td><td>{item.bytes}</td>"
        f"<td><code>{item.sha256}</code></td></tr>"
        for item in result.artifacts
    )
    execution = ""
    if inspection.execution is not None:
        dependency_rows = "\n".join(
            f"<tr><td>{escape(item.name)}</td><td>{escape(item.version)}</td></tr>"
            for item in inspection.execution.dependencies
        )
        execution_rows = _html_rows(
            [
                ("Workspace", inspection.execution.workspace_id),
                ("Producer revision", inspection.execution.producer_revision),
                ("Release", inspection.execution.release_artifact_name),
                ("Release SHA-256", inspection.execution.release_artifact_sha256),
                (
                    "Runtime package tree SHA-256",
                    inspection.execution.runtime_package_tree_sha256,
                ),
                ("Receipt SHA-256", inspection.execution.receipt_sha256),
                ("Manifest SHA-256", inspection.execution.manifest_sha256),
                ("Started", inspection.execution.started_at_utc),
                ("Finished", inspection.execution.finished_at_utc),
                ("Duration seconds", inspection.execution.duration_seconds),
                ("Python", inspection.execution.python_version),
                (
                    "Platform",
                    f"{inspection.execution.platform_system} "
                    f"{inspection.execution.platform_machine}",
                ),
            ]
        )
        execution = _details(
            "Execution provenance",
            f"<table><tbody>{execution_rows}</tbody></table>"
            "<h3>Dependencies</h3><table><thead><tr><th>Name</th><th>Version</th></tr>"
            f"</thead><tbody>{dependency_rows}</tbody></table>",
        )
    semantic_rows = _html_rows(
        [
            ("Package", result.run.package_version),
            ("Runtime contract", result.run.runtime_contract),
            ("Build lock SHA-256", result.run.build_lock_sha256),
            ("Scoring", result.problem.scoring_semantics),
            ("Objective", result.problem.objective_semantics),
            ("Tie break", result.problem.tie_break_semantics),
            ("Strands", result.problem.strands),
        ]
    )
    motif_details = _details(
        "Motif models and semantic contract",
        f"<table><tbody>{semantic_rows}</tbody></table>"
        '<div class="table-wrap"><table><thead><tr><th>Motif</th><th>Width</th>'
        "<th>Model digest</th><th>Source</th><th>Source digest</th>"
        "<th>Canonical file</th><th>Canonical digest</th><th>Conversion</th><th>Prior</th>"
        f"</tr></thead><tbody>{motif_rows}</tbody></table></div>",
    )
    match_details = _details(
        "Per-candidate motif matches",
        f'{match_limit}<div class="table-wrap"><table><thead><tr>'
        "<th>Rank</th><th>Motif</th><th>Start</th><th>End</th><th>Strand</th>"
        "<th>Matched sequence</th><th>Raw score</th><th>Normalized score</th>"
        f"</tr></thead><tbody>{match_rows}</tbody></table></div>",
    )
    diagnostic_rows = _html_rows(
        [
            ("Engine", result.run.search_engine),
            ("Engine version", result.run.search_engine_version),
            ("RNG", result.run.rng),
            ("Search validation", result.run.search_validation_status),
            ("Evaluation budget", result.run.evaluations_requested),
            ("Evaluator calls", result.run.evaluation_count),
            ("Unique evaluations", result.run.unique_evaluations),
            ("Seed", result.run.seed),
            ("Requested minimum distance", result.run.min_distance_requested),
            ("Distance work", distance.base_comparisons),
            ("Distance limit", distance.computation_limit),
            ("Closest candidate IDs", distance.closest_candidate_ids),
            ("Restart final scores", result.diagnostics.restart_final_scores),
        ]
    )
    diagnostics_details = _details(
        "Optimizer diagnostics",
        f"<table><tbody>{diagnostic_rows}</tbody></table>"
        f"<h3>Best-score checkpoints</h3>{checkpoint_limit}"
        "<table><thead><tr><th>Evaluations</th>"
        f"<th>Best score</th></tr></thead><tbody>{checkpoint_rows}</tbody></table>"
        "<h3>Proposal summary</h3><table><thead><tr><th>Move</th><th>Attempted</th>"
        "<th>Accepted</th><th>Rate</th></tr></thead>"
        f"<tbody>{proposal_rows}</tbody></table>",
    )
    artifact_details = _details(
        "Artifact integrity",
        '<div class="table-wrap"><table><thead><tr><th>Key</th><th>Role</th>'
        "<th>Format</th><th>Path</th><th>Bytes</th><th>SHA-256</th></tr></thead>"
        f"<tbody>{artifact_rows}</tbody></table></div>",
    )
    candidate_map = render_candidate_match_map(result.portfolio.candidates[0]).decode("utf-8")
    portfolio_profile = render_portfolio_balance_profile(result.portfolio.candidates).decode(
        "utf-8"
    )
    search_progress = render_search_progress(result.diagnostics).decode("utf-8")
    body = f"""
    <h2>Start here</h2><table><tbody>{start_rows}</tbody></table>
    <h2>How the result was built</h2>
    <ol class="flow"><li><strong>Model</strong><span>Validate explicit motif models.</span></li>
    <li><strong>Scan</strong><span>Find one best match per motif.</span></li>
    <li><strong>Balance</strong><span>Use the weakest normalized motif score.</span></li>
    <li><strong>Select</strong><span>Return the exact deterministic portfolio.</span></li></ol>
    <h2>Where motif scores land</h2><div class="visual">{candidate_map}</div>
    <p>Spans share the candidate coordinate axis, so overlap is visible. A span is a best-match
    coordinate record; it is not evidence of biological occupancy.</p>
    <h2>Portfolio balance</h2><div class="visual">{portfolio_profile}</div>
    <p>Rows compare candidates only within this verified run and under the same declared motif
    models and score semantics.</p>
    <h2>Best-so-far search progress</h2><div class="visual">{search_progress}</div>
    <p>This is best-so-far progress at recorded checkpoints, not a full optimizer trace or a
    convergence guarantee.</p>
    <h2>Candidate portfolio</h2>{candidate_limit}<div class="table-wrap"><table><thead><tr>
    <th>Rank</th><th>ID</th><th>Sequence</th><th>Balance score</th><th>Limiting motifs</th>
    </tr></thead><tbody>{candidate_rows}</tbody></table></div>
    {motif_details}
    {match_details}
    {diagnostics_details}
    {execution}
    {artifact_details}
    """
    title = "Motif Balance result inspection"
    scope = " ".join(result.claim_scope)
    document = f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>{escape(title)}</title><style>
body{{margin:0;background:#fbfcfa;color:#172021;font:16px/1.5 system-ui,sans-serif}}
main{{max-width:1180px;margin:auto;padding:3rem 1.25rem 5rem}}
h1{{font-size:2.5rem;margin:0 0 .5rem}}
.status{{color:#40504e;margin-bottom:2rem}}
h2{{margin-top:2.5rem;border-top:1px solid #d9dfdd;padding-top:1rem}}
details{{border-top:1px solid #d9dfdd;margin-top:1.5rem;padding-top:1rem}}
summary{{cursor:pointer;font-weight:650;font-size:1.15rem}}
.detail{{padding-top:.8rem}}
.table-wrap{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:.9rem}}
th{{text-align:left;color:#5b6667}}
th,td{{border-bottom:1px solid #d9dfdd;padding:.55rem;vertical-align:top}}
code{{font: .82rem/1.4 ui-monospace,monospace}}
.sequence{{letter-spacing:.05em;white-space:nowrap}}
.visual{{border:1px solid #d9dfdd;background:#fbfcfa;margin:1rem 0;padding:.5rem}}
.visual svg{{display:block;width:100%;height:auto}}
.flow{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.75rem;padding:0}}
.flow li{{list-style:none;border-top:3px solid #d97757;padding:.65rem 0}}
.flow span{{display:block;color:#5b6667;font-size:.9rem}}
.scope{{border:1px solid #d9dfdd;padding:1rem 1.2rem;margin-top:2rem}}
@media(max-width:720px){{.flow{{grid-template-columns:1fr 1fr}}}}
</style></head><body><main><h1>{escape(title)}</h1>
<p class=\"status\">Integrity: <strong>{escape(inspection.integrity_status)}</strong> · Trust basis:
<strong>{escape(inspection.trust_basis)}</strong></p>{body}
<div class=\"scope\"><strong>Interpretation boundary.</strong> {escape(scope)}</div>
</main></body></html>"""
    return document.encode()


def catalog_html(value: ResultCatalog) -> bytes:
    """Render a bounded current-result catalog as a compact review table."""

    rows = "\n".join(
        "<tr>"
        f"<td>{escape(entry.entry_id)}</td>"
        f"<td>{escape(entry.subject_kind)}</td>"
        f"<td>{escape(entry.integrity_status)}</td>"
        f"<td><code>{escape(entry.problem_id)}</code></td>"
        f"<td>{escape(', '.join(entry.motif_ids))}"
        "</td>"
        f"<td>{entry.returned_count}</td>"
        f"<td>{entry.score_min:.17g} .. {entry.score_max:.17g}</td>"
        f"<td>{escape(entry.distance_status)}</td>"
        f"<td>{escape(entry.completion_status)}</td></tr>"
        for entry in value.entries
    )
    document = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Motif Balance result catalog</title><style>
body{{margin:0;background:#fbfcfa;color:#172021;font:16px/1.5 system-ui,sans-serif}}
main{{max-width:1280px;margin:auto;padding:3rem 1.25rem 5rem}}h1{{font-size:2.5rem}}
.table-wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;font-size:.88rem}}
th{{text-align:left;color:#5b6667}}
th,td{{border-bottom:1px solid #d9dfdd;padding:.55rem;vertical-align:top}}
code{{font:.82rem/1.4 ui-monospace,monospace}}</style></head><body><main>
<h1>Motif Balance result catalog</h1>
<p>Explicit current results only. This table reports compatibility context; it does not rank
quality, define a cohort, or accept evidence.</p><div class="table-wrap"><table><thead><tr>
<th>Entry</th><th>Kind</th><th>Integrity</th><th>Problem</th><th>Motifs</th><th>Count</th>
<th>Score range</th><th>Distance</th><th>Completion</th></tr></thead>
<tbody>{rows}</tbody></table></div>
</main></body></html>"""
    return document.encode()
