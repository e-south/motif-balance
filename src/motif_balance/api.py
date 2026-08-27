from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Literal

import yaml

from motif_balance.artifacts import (
    BundleSnapshot,
    artifact_records,
    base_artifact_payloads,
    bundle_id,
    candidates_fasta,
    manifest_bytes,
    read_bundle_snapshot,
    write_bundle,
)
from motif_balance.compile import compile_design, sequence_space_at_most
from motif_balance.constants import (
    BUILD_LOCK_SHA256,
    MAX_BUNDLE_ARTIFACT_BYTES,
    MAX_INPUT_BYTES,
    PACKAGE_VERSION,
    RNG_NAME,
    RUNTIME_CONTRACT,
    SEARCH_ENGINE,
    SEARCH_ENGINE_VERSION,
)
from motif_balance.errors import ArtifactError, InvalidDesign, InvalidMotif
from motif_balance.formats import convert_jaspar, read_motif
from motif_balance.formats.structured import load_yaml_unique
from motif_balance.inspection import (
    ResultCatalog,
    ResultInspection,
    VerifiedResultSource,
    build_catalog,
    project_execution,
    project_result,
    render_candidate_svg,
    render_catalog_html,
    render_html,
    render_portfolio_svg,
    render_search_svg,
    render_text,
)
from motif_balance.inspection import (
    render_inspection_json as _render_inspection_json,
)
from motif_balance.model import (
    ArtifactDigest,
    Candidate,
    DesignSpec,
    Evaluation,
    ExecutionBundleResource,
    ExecutionReleaseResource,
    ExecutionResource,
    ExecutionWorkspace,
    MotifMatch,
    MotifModel,
    PortfolioRecord,
    RunManifest,
)
from motif_balance.receipt import (
    build_execution_receipt,
    parse_execution_receipt,
    parse_execution_workspace,
    receipt_bytes,
    validate_receipt_against_portfolio,
    workspace_bytes,
    workspace_id,
)
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
    "ResultCatalog",
    "ResultInspection",
    "build_result_catalog",
    "compile_spec",
    "convert_motif",
    "design",
    "execute_design_workspace",
    "inspect_result",
    "load_spec",
    "read_motif",
    "read_portfolio",
    "render_bundle_report",
    "render_inspection_html",
    "render_result_catalog_html",
    "score",
    "summarize_inspection",
    "verify_bundle",
    "verify_execution_workspace",
]


class Portfolio(PortfolioRecord):
    """Public immutable portfolio with side-effecting convenience operations."""

    def to_fasta(self) -> str:
        return candidates_fasta(self.candidates).decode()

    def write(self, path: str | Path) -> Path:
        if (
            self.manifest.schema_version != "run-manifest/v3"
            or self.manifest.package_version != PACKAGE_VERSION
            or self.manifest.runtime_contract != RUNTIME_CONTRACT
            or self.manifest.build_lock_sha256 != BUILD_LOCK_SHA256
        ):
            raise ArtifactError("bundle publication requires current package provenance")
        _verify_scientific_replay(self)
        return write_bundle(self, Path(path), _bundle_payloads(self.spec, self.candidates))


def _bundle_payloads(
    spec: DesignSpec,
    candidates: tuple[Candidate, ...],
) -> dict[str, bytes]:
    return base_artifact_payloads(spec, candidates)


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
        payload = load_yaml_unique(raw)
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


def _planned_search_kind(spec: DesignSpec) -> str:
    """Return the bounded search classification used by the CLI preflight."""

    return (
        "exhaustive"
        if sequence_space_at_most(spec.length, spec.evaluations) is not None
        else "annealed"
    )


def convert_motif(
    path: str | Path,
    *,
    motif_id: str,
    background: tuple[float, float, float, float],
    prior_weight: float,
) -> MotifModel:
    return convert_jaspar(
        path,
        motif_id=motif_id,
        background=background,
        prior_weight=prior_weight,
    )


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
        search_validation_status=result.search_validation_status,
        search_diagnostics=result.diagnostics,
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

    sequence_space = sequence_space_at_most(portfolio.spec.length, portfolio.spec.evaluations)
    if sequence_space is not None:
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
            "contract_tested",
            portfolio.spec.evaluations,
        )
    actual_metadata = (
        portfolio.manifest.search_engine,
        portfolio.manifest.search_engine_version,
        portfolio.manifest.rng,
        portfolio.manifest.completion_status,
        portfolio.manifest.search_validation_status,
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
    portfolio, _snapshot = _read_portfolio_snapshot(
        directory,
        expected_bundle_id=expected_bundle_id,
    )
    return portfolio


def _read_portfolio_snapshot(
    directory: str | Path,
    *,
    expected_bundle_id: str | None = None,
) -> tuple[Portfolio, BundleSnapshot]:
    snapshot = read_bundle_snapshot(directory)
    portfolio = Portfolio.model_validate(snapshot.portfolio.model_dump(mode="python"))
    if expected_bundle_id is not None and portfolio.manifest.bundle_id != expected_bundle_id:
        raise ArtifactError("bundle identity does not match the externally expected identity")
    _verify_scientific_replay(portfolio)
    return portfolio, snapshot


def _snapshot_artifacts(
    snapshot: BundleSnapshot,
) -> tuple[tuple[ArtifactDigest, bytes], ...]:
    return tuple(
        (record, snapshot.payload(record.path)) for record in snapshot.portfolio.manifest.artifacts
    )


def verify_bundle(
    directory: str | Path,
    *,
    expected_bundle_id: str | None = None,
) -> str:
    return read_portfolio(
        directory,
        expected_bundle_id=expected_bundle_id,
    ).manifest.bundle_id


def _write_new_file(path: Path, payload: bytes, *, label: str) -> None:
    temporary: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path, follow_symlinks=False)
    except FileExistsError as exc:
        raise ArtifactError(
            f"Refusing to replace existing {label} '{path.name}'.",
            field="out",
            hint="Choose a new output path.",
        ) from exc
    except OSError as exc:
        raise ArtifactError(
            f"Unable to write {label} '{path.name}'.",
            field="out",
            hint="Choose a writable output path whose parent directory exists.",
        ) from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def render_bundle_report(directory: str | Path, out: str | Path) -> str:
    root = Path(directory)
    destination = Path(out)
    if destination.resolve(strict=False).is_relative_to(root.resolve()):
        raise ArtifactError(
            "Derived report output must remain outside the verified bundle.",
            field="out",
            hint="Choose a separate review or handoff directory.",
        )
    inspection = inspect_result(root, kind="bundle")
    _write_new_file(
        destination,
        render_html(inspection),
        label="report",
    )
    return inspection.run.bundle_id


def inspect_result(
    path: str | Path,
    *,
    kind: Literal["bundle", "execution"],
    expected_bundle_id: str | None = None,
    expected_workspace_id: str | None = None,
    expected_receipt_sha256: str | None = None,
    expected_release_sha256: str | None = None,
    expected_producer_revision: str | None = None,
) -> ResultInspection:
    """Return a typed, read-only projection after kind-appropriate verification."""

    root = Path(path)
    execution_anchors = (
        expected_workspace_id,
        expected_receipt_sha256,
        expected_release_sha256,
        expected_producer_revision,
    )
    if kind == "bundle":
        if any(value is not None for value in execution_anchors):
            raise ArtifactError("execution trust anchors cannot be used for a bundle inspection")
        portfolio, snapshot = _read_portfolio_snapshot(
            root,
            expected_bundle_id=expected_bundle_id,
        )
        return project_result(
            VerifiedResultSource(
                portfolio=portfolio,
                canonical_manifest=snapshot.payload("manifest.json"),
                artifacts=_snapshot_artifacts(snapshot),
                subject_kind=kind,
                integrity_state=(
                    "externally_verified" if expected_bundle_id else "self_consistent"
                ),
                trust_basis=("external_bundle_id" if expected_bundle_id else "self_consistent"),
                checked_identities=(("bundle_id",) if expected_bundle_id else ()),
            )
        )
    if kind != "execution":
        raise ArtifactError(f"unsupported inspection kind '{kind}'")
    if expected_bundle_id is not None:
        raise ArtifactError("bundle trust anchor cannot replace execution-workspace anchors")
    supplied = tuple(value is not None for value in execution_anchors)
    if any(supplied) and not all(supplied):
        raise ArtifactError("execution inspection requires all four external trust anchors or none")
    index_before = _read_workspace_file(root, "execution-workspace.json")
    workspace = parse_execution_workspace(index_before)
    anchors: tuple[str, str, str, str]
    trust_basis: Literal["self_consistent", "external_execution_identities"]
    checked: tuple[str, ...]
    integrity_status: Literal["verified", "readable_untrusted"]
    if all(supplied):
        assert expected_workspace_id is not None
        assert expected_receipt_sha256 is not None
        assert expected_release_sha256 is not None
        assert expected_producer_revision is not None
        anchors = (
            expected_workspace_id,
            expected_receipt_sha256,
            expected_release_sha256,
            expected_producer_revision,
        )
        trust_basis = "external_execution_identities"
        checked = ("workspace_id", "receipt_sha256", "release_sha256", "producer_revision")
        integrity_status = "verified"
    else:
        anchors = (
            workspace.workspace_id,
            workspace.receipt.sha256,
            workspace.release.sha256,
            workspace.release.producer_revision,
        )
        trust_basis = "self_consistent"
        checked = ()
        integrity_status = "readable_untrusted"
    verify_execution_workspace(
        root,
        expected_workspace_id=anchors[0],
        expected_receipt_sha256=anchors[1],
        expected_release_sha256=anchors[2],
        expected_producer_revision=anchors[3],
    )
    # Bind the exact bytes projected below, not only a preceding/following
    # verification read. Otherwise a concurrent substitution between reads
    # could publish unattested receipt fields in a verified inspection.
    receipt_payload = _verify_resource(root, workspace.receipt)
    receipt = parse_execution_receipt(receipt_payload)
    portfolio, snapshot = _read_portfolio_snapshot(
        root / "bundle",
        expected_bundle_id=workspace.bundle.bundle_id,
    )
    verify_execution_workspace(
        root,
        expected_workspace_id=anchors[0],
        expected_receipt_sha256=anchors[1],
        expected_release_sha256=anchors[2],
        expected_producer_revision=anchors[3],
    )
    if _read_workspace_file(root, "execution-workspace.json") != index_before:
        raise ArtifactError("execution workspace changed during inspection")
    return project_result(
        VerifiedResultSource(
            portfolio=portfolio,
            canonical_manifest=snapshot.payload("manifest.json"),
            artifacts=_snapshot_artifacts(snapshot),
            subject_kind=kind,
            integrity_state=(
                "externally_verified" if integrity_status == "verified" else "readable_untrusted"
            ),
            trust_basis=trust_basis,
            checked_identities=checked,
            execution=project_execution(workspace, receipt),
        )
    )


def build_result_catalog(entries: dict[str, ResultInspection]) -> ResultCatalog:
    """Build a deterministic derived catalog from explicit inspected subjects."""

    return build_catalog(entries)


def summarize_inspection(inspection: ResultInspection) -> str:
    """Render a path-independent terminal summary for one inspection."""

    return render_text(inspection)


def render_inspection_html(inspection: ResultInspection) -> bytes:
    """Render one inspection as a self-contained, script-free HTML view."""

    return render_html(inspection)


def render_inspection_json(inspection: ResultInspection) -> bytes:
    """Render one complete typed inspection as deterministic JSON."""

    return _render_inspection_json(inspection)


def render_inspection_svg(
    inspection: ResultInspection,
    *,
    view: Literal["candidate", "portfolio", "search"],
    candidate_rank: int = 1,
) -> bytes:
    """Render one product-owned SVG view from the immutable inspection."""

    if view == "candidate":
        return render_candidate_svg(inspection, candidate_rank=candidate_rank)
    if view == "portfolio":
        return render_portfolio_svg(inspection)
    if view == "search":
        payload = render_search_svg(inspection)
        if payload is None:
            raise ArtifactError("this result does not contain a recorded search view")
        return payload
    raise ArtifactError(f"unsupported inspection view '{view}'")


def render_result_catalog_html(value: ResultCatalog) -> bytes:
    """Render a bounded catalog of current result inspections."""

    return render_catalog_html(value)


def _resolved_spec_bytes(spec: DesignSpec) -> bytes:
    payload = spec.model_dump(mode="json", exclude={"motifs"})
    payload["motifs"] = {motif.motif_id: motif.model_dump(mode="json") for motif in spec.motifs}
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()


def _resource(path: str, payload: bytes) -> ExecutionResource:
    return ExecutionResource(
        path=path, sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload)
    )


def _read_release(path: Path) -> bytes:
    if path.is_symlink():
        raise ArtifactError("release artifact must not be a symbolic link")
    try:
        if not path.is_file() or path.stat().st_size > MAX_BUNDLE_ARTIFACT_BYTES:
            raise ArtifactError(
                f"release artifact must be a file no larger than {MAX_BUNDLE_ARTIFACT_BYTES} bytes"
            )
        payload = path.read_bytes()
    except OSError as exc:
        raise ArtifactError(f"unable to read release artifact: {exc}") from exc
    return payload


def _package_tree_digest(entries: dict[str, bytes]) -> str:
    records = [
        {"path": path, "sha256": hashlib.sha256(payload).hexdigest()}
        for path, payload in sorted(entries.items())
    ]
    return hashlib.sha256(_canonical_json_bytes(records)).hexdigest()


def _canonical_json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _release_package_tree(payload: bytes) -> dict[str, bytes]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise ArtifactError("release artifact is not a valid wheel archive") from exc
    entries: dict[str, bytes] = {}
    with archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        names = [member.filename for member in members]
        if len(names) != len(set(names)):
            raise ArtifactError("release artifact contains duplicate wheel members")
        total_bytes = sum(member.file_size for member in members)
        if total_bytes > MAX_BUNDLE_ARTIFACT_BYTES:
            raise ArtifactError("release wheel contents exceed the byte limit")
        for member in members:
            path = PurePosixPath(member.filename)
            if (
                member.filename.startswith("/")
                or "\\" in member.filename
                or any(part in {"", ".", ".."} for part in path.parts)
            ):
                raise ArtifactError("release artifact contains an unsafe wheel path")
            if stat.S_ISLNK(member.external_attr >> 16):
                raise ArtifactError("release artifact contains a symbolic-link wheel member")
        metadata_members = [
            member for member in members if member.filename.endswith(".dist-info/METADATA")
        ]
        wheel_members = [
            member for member in members if member.filename.endswith(".dist-info/WHEEL")
        ]
        if len(metadata_members) != 1 or len(wheel_members) != 1:
            raise ArtifactError("release artifact does not contain one wheel metadata record")
        dist_info = metadata_members[0].filename.removesuffix("METADATA")
        if wheel_members[0].filename != f"{dist_info}WHEEL":
            raise ArtifactError("release artifact wheel metadata directories do not match")
        record_name = f"{dist_info}RECORD"
        if names.count(record_name) != 1:
            raise ArtifactError("release artifact does not contain one RECORD")
        for name in names:
            allowed_metadata = name in {
                f"{dist_info}METADATA",
                f"{dist_info}WHEEL",
                f"{dist_info}RECORD",
                f"{dist_info}entry_points.txt",
            } or name.startswith(f"{dist_info}licenses/")
            if not name.startswith("motif_balance/") and not allowed_metadata:
                raise ArtifactError(f"release artifact contains unexpected wheel member '{name}'")
        try:
            payloads = {member.filename: archive.read(member) for member in members}
        except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
            raise ArtifactError("release artifact contains unreadable wheel members") from exc
        metadata = BytesParser(policy=policy.default).parsebytes(
            payloads[metadata_members[0].filename]
        )
        normalized_name = re.sub(r"[-_.]+", "-", str(metadata.get("Name", ""))).lower()
        if normalized_name != "motif-balance" or metadata.get("Version") != PACKAGE_VERSION:
            raise ArtifactError("release wheel identity does not match this package build")
        expected_entry_points = b"[console_scripts]\nmotif-balance = motif_balance.cli:app\n"
        if payloads.get(f"{dist_info}entry_points.txt") != expected_entry_points:
            raise ArtifactError("release artifact console entry point is missing or unexpected")
        try:
            record_rows = list(csv.reader(io.StringIO(payloads[record_name].decode("utf-8"))))
        except (UnicodeDecodeError, csv.Error) as exc:
            raise ArtifactError("release artifact RECORD is not valid UTF-8 CSV") from exc
        if len(record_rows) != len(names) or any(len(row) != 3 for row in record_rows):
            raise ArtifactError("release artifact RECORD is malformed")
        if {row[0] for row in record_rows} != set(names):
            raise ArtifactError("release artifact RECORD inventory mismatch")
        for name, digest, size in record_rows:
            if name == record_name:
                if digest or size:
                    raise ArtifactError("release artifact RECORD must not hash itself")
                continue
            expected_digest = (
                base64.urlsafe_b64encode(hashlib.sha256(payloads[name]).digest())
                .rstrip(b"=")
                .decode()
            )
            if digest != f"sha256={expected_digest}" or size != str(len(payloads[name])):
                raise ArtifactError(f"release artifact RECORD mismatch for '{name}'")
        for name, member_payload in payloads.items():
            if not name.startswith("motif_balance/"):
                continue
            relative = name.removeprefix("motif_balance/")
            parts = Path(relative).parts
            if not relative or any(part in {"", ".", ".."} for part in parts):
                raise ArtifactError("release artifact contains an unsafe package path")
            entries[relative] = member_payload
    if "__init__.py" not in entries:
        raise ArtifactError("release artifact does not contain the motif_balance package")
    return entries


def _runtime_package_tree() -> dict[str, bytes]:
    package_root = Path(__file__).parent
    entries: dict[str, bytes] = {}
    for path in sorted(package_root.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink() or not path.is_file():
            raise ArtifactError("runtime package tree contains an unsafe file")
        relative = path.relative_to(package_root).as_posix()
        entries[relative] = path.read_bytes()
    return entries


def _attest_release_runtime(release_payload: bytes) -> str:
    release_tree = _release_package_tree(release_payload)
    runtime_tree = _runtime_package_tree()
    if release_tree != runtime_tree:
        raise ArtifactError("release artifact package tree does not match the running package")
    return _package_tree_digest(runtime_tree)


def _validate_execution_identity(release_path: Path, producer_revision: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", producer_revision):
        raise ArtifactError("producer revision must be a lowercase 40-character Git commit")
    if release_path.name in {"design-spec.json", "SHA256SUMS"}:
        raise ArtifactError("release artifact name collides with a reserved execution input")
    if release_path.suffix != ".whl":
        raise ArtifactError("release artifact must be a wheel file")


def execute_design_workspace(
    specification: str | Path,
    output: str | Path,
    *,
    producer_revision: str,
    release_artifact: str | Path,
) -> ExecutionWorkspace:
    """Execute and atomically publish input, release, bundle, and runtime receipt."""

    destination = Path(output)
    release_path = Path(release_artifact)
    _validate_execution_identity(release_path, producer_revision)
    if destination.exists() or destination.is_symlink():
        raise ArtifactError(
            f"execution workspace already exists or is unsafe: '{destination.name}'"
        )
    release_payload = _read_release(release_path)
    runtime_package_tree_sha256 = _attest_release_runtime(release_payload)
    started_at = datetime.now(UTC)
    spec = load_spec(specification)
    normalized_spec = _resolved_spec_bytes(spec)
    portfolio = design(spec)
    if _attest_release_runtime(release_payload) != runtime_package_tree_sha256:
        raise ArtifactError("runtime package tree changed during execution")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(
            tempfile.mkdtemp(prefix=f".{destination.name}.tmp-", dir=destination.parent)
        )
    except OSError as exc:
        raise ArtifactError("unable to create the execution publication directory") from exc
    try:
        inputs = temporary / "inputs"
        inputs.mkdir()
        input_path = inputs / "design-spec.json"
        input_path.write_bytes(normalized_spec)
        copied_release = inputs / release_path.name
        copied_release.write_bytes(release_payload)
        portfolio.write(temporary / "bundle")
        finished_at = datetime.now(UTC)
        manifest_payload = manifest_bytes(portfolio.manifest)
        release_sha256 = hashlib.sha256(release_payload).hexdigest()
        input_sha256 = hashlib.sha256(normalized_spec).hexdigest()
        receipt = build_execution_receipt(
            portfolio,
            manifest_payload=manifest_payload,
            producer_revision=producer_revision,
            release_artifact_name=release_path.name,
            release_artifact_sha256=release_sha256,
            runtime_package_tree_sha256=runtime_package_tree_sha256,
            normalized_design_sha256=input_sha256,
            started_at=started_at,
            finished_at=finished_at,
        )
        receipt_payload = receipt_bytes(receipt)
        (temporary / "execution-receipt.json").write_bytes(receipt_payload)
        checksums_payload = (
            f"{input_sha256}  inputs/design-spec.json\n"
            f"{release_sha256}  inputs/{release_path.name}\n"
        ).encode()
        (inputs / "SHA256SUMS").write_bytes(checksums_payload)
        provisional = ExecutionWorkspace(
            workspace_id="execution-000000000000000000000000",
            input=_resource("inputs/design-spec.json", normalized_spec),
            release=ExecutionReleaseResource(
                path=f"inputs/{release_path.name}",
                sha256=release_sha256,
                bytes=len(release_payload),
                producer_revision=producer_revision,
            ),
            checksums=_resource("inputs/SHA256SUMS", checksums_payload),
            bundle=ExecutionBundleResource(
                bundle_id=portfolio.manifest.bundle_id,
                manifest_sha256=hashlib.sha256(manifest_payload).hexdigest(),
            ),
            receipt=_resource("execution-receipt.json", receipt_payload),
        )
        workspace = provisional.model_copy(update={"workspace_id": workspace_id(provisional)})
        (temporary / "execution-workspace.json").write_bytes(workspace_bytes(workspace))
        verified = verify_execution_workspace(
            temporary,
            expected_workspace_id=workspace.workspace_id,
            expected_receipt_sha256=workspace.receipt.sha256,
            expected_release_sha256=release_sha256,
            expected_producer_revision=producer_revision,
        )
        if verified != workspace.workspace_id:
            raise ArtifactError("execution workspace round-trip changed its identity")
        if destination.exists() or destination.is_symlink():
            raise ArtifactError(
                f"execution workspace already exists or is unsafe: '{destination.name}'"
            )
        os.rename(temporary, destination)
        return workspace
    except OSError as exc:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise ArtifactError("unable to publish the execution workspace") from exc
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def _read_workspace_file(root: Path, relative: str) -> bytes:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise ArtifactError(f"execution workspace contains unsafe resource '{relative}'")
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ArtifactError(f"unable to read execution resource '{relative}': {exc}") from exc
    if len(payload) > MAX_BUNDLE_ARTIFACT_BYTES:
        raise ArtifactError(f"execution resource '{relative}' exceeds the byte limit")
    return payload


def _verify_resource(root: Path, resource: ExecutionResource) -> bytes:
    payload = _read_workspace_file(root, resource.path)
    if len(payload) != resource.bytes or hashlib.sha256(payload).hexdigest() != resource.sha256:
        raise ArtifactError(f"execution resource digest mismatch for '{resource.path}'")
    return payload


def verify_execution_workspace(
    directory: str | Path,
    *,
    expected_workspace_id: str,
    expected_receipt_sha256: str,
    expected_release_sha256: str,
    expected_producer_revision: str,
) -> str:
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise ArtifactError("execution workspace directory is missing or unsafe")
    root_names = {entry.name for entry in root.iterdir()}
    if root_names != {"bundle", "inputs", "execution-receipt.json", "execution-workspace.json"}:
        raise ArtifactError("execution workspace root inventory mismatch")
    index_payload = _read_workspace_file(root, "execution-workspace.json")
    workspace = parse_execution_workspace(index_payload)
    if workspace.workspace_id != expected_workspace_id:
        raise ArtifactError("execution workspace does not match the externally expected identity")
    if workspace.receipt.sha256 != expected_receipt_sha256:
        raise ArtifactError("execution receipt does not match the externally expected digest")
    if workspace.release.sha256 != expected_release_sha256:
        raise ArtifactError("release artifact does not match the externally expected digest")
    if workspace.release.producer_revision != expected_producer_revision:
        raise ArtifactError("release artifact does not match the expected producer revision")
    if workspace.input.path != "inputs/design-spec.json":
        raise ArtifactError("execution workspace input path is not canonical")
    if workspace.checksums.path != "inputs/SHA256SUMS":
        raise ArtifactError("execution workspace checksum path is not canonical")
    if workspace.receipt.path != "execution-receipt.json":
        raise ArtifactError("execution workspace receipt path is not canonical")
    release_name = Path(workspace.release.path).name
    if workspace.release.path != f"inputs/{release_name}":
        raise ArtifactError("execution workspace release path is not canonical")
    inputs = root / "inputs"
    if inputs.is_symlink() or not inputs.is_dir():
        raise ArtifactError("execution workspace inputs directory is unsafe")
    if {entry.name for entry in inputs.iterdir()} != {
        "design-spec.json",
        "SHA256SUMS",
        release_name,
    }:
        raise ArtifactError("execution workspace input inventory mismatch")
    input_payload = _verify_resource(root, workspace.input)
    release_payload = _verify_resource(root, workspace.release)
    checksums_payload = _verify_resource(root, workspace.checksums)
    receipt_payload = _verify_resource(root, workspace.receipt)
    expected_checksums = (
        f"{hashlib.sha256(input_payload).hexdigest()}  inputs/design-spec.json\n"
        f"{hashlib.sha256(release_payload).hexdigest()}  inputs/{release_name}\n"
    ).encode()
    if checksums_payload != expected_checksums:
        raise ArtifactError("execution workspace checksum file is not canonical")
    manifest_before = _read_workspace_file(root, "bundle/manifest.json")
    portfolio = read_portfolio(root / "bundle", expected_bundle_id=workspace.bundle.bundle_id)
    manifest_after = _read_workspace_file(root, "bundle/manifest.json")
    if manifest_before != manifest_after:
        raise ArtifactError("bundle manifest changed during execution-workspace verification")
    if hashlib.sha256(manifest_before).hexdigest() != workspace.bundle.manifest_sha256:
        raise ArtifactError("execution workspace bundle manifest digest mismatch")
    if _resolved_spec_bytes(portfolio.spec) != input_payload:
        raise ArtifactError("execution workspace input does not match the verified bundle")
    receipt = parse_execution_receipt(receipt_payload)
    if _package_tree_digest(_release_package_tree(release_payload)) != (
        receipt.runtime_package_tree_sha256
    ):
        raise ArtifactError("execution receipt runtime package-tree digest mismatch")
    if receipt.normalized_design_sha256 != workspace.input.sha256:
        raise ArtifactError("execution receipt input digest mismatch")
    if receipt.release_artifact_name != release_name:
        raise ArtifactError("execution receipt release name mismatch")
    validate_receipt_against_portfolio(
        receipt,
        portfolio,
        manifest_payload=manifest_before,
        expected_release_sha256=expected_release_sha256,
        expected_producer_revision=expected_producer_revision,
    )
    return workspace.workspace_id
