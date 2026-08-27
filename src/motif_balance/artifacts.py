from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import stat
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from motif_balance.compile import build_run_id, compile_design, sequence_space_at_most
from motif_balance.constants import (
    MAX_BUNDLE_ARTIFACT_BYTES,
    MAX_BUNDLE_ROWS,
    MAX_INPUT_BYTES,
    RNG_NAME,
    SEARCH_ENGINE,
    SEARCH_ENGINE_VERSION,
)
from motif_balance.errors import ArtifactError
from motif_balance.model import (
    ArtifactDigest,
    Candidate,
    DesignSpec,
    MotifMatch,
    MotifModel,
    PortfolioRecord,
    RunManifest,
)
from motif_balance.scoring import evaluate
from motif_balance.selection import candidate_id_for_sequence

_CANONICAL_FILES = {
    "design.json",
    "motifs.json",
    "candidates.tsv",
    "matches.tsv",
    "manifest.json",
}
_DERIVED_FILES = {"candidates.fasta"}
_V3_FILES = _CANONICAL_FILES | _DERIVED_FILES
_V2_FILES = _V3_FILES | {"report.html"}


def _schema_files(manifest: RunManifest) -> set[str]:
    if manifest.schema_version == "run-manifest/v2":
        return _V2_FILES
    return _V3_FILES


def _json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _design_payload(spec: DesignSpec) -> dict[str, object]:
    return {
        "schema_version": spec.schema_version,
        "motifs": [
            {"motif_id": motif.motif_id, "model_digest": motif.model_digest}
            for motif in spec.motifs
        ],
        "length": spec.length,
        "count": spec.count,
        "strands": spec.strands,
        "evaluations": spec.evaluations,
        "seed": spec.seed,
        "min_distance": spec.min_distance,
        "scoring_semantics": spec.scoring_semantics,
        "objective_semantics": spec.objective_semantics,
        "tie_break_semantics": spec.tie_break_semantics,
    }


def _motifs_payload(spec: DesignSpec) -> dict[str, object]:
    motifs = []
    for motif in spec.motifs:
        payload = motif.model_dump(mode="json")
        payload["width"] = motif.width
        payload["model_digest"] = motif.model_digest
        motifs.append(payload)
    return {"schema_version": "motif-collection/v1", "motifs": motifs}


def _tsv_bytes(fieldnames: tuple[str, ...], rows: list[dict[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def candidates_tsv(candidates: tuple[Candidate, ...]) -> bytes:
    rows = [
        {
            "candidate_id": candidate.candidate_id,
            "rank": candidate.rank,
            "sequence": candidate.sequence,
            "length": len(candidate.sequence),
            "balance_score": format(candidate.balance_score, ".17g"),
        }
        for candidate in candidates
    ]
    return _tsv_bytes(("candidate_id", "rank", "sequence", "length", "balance_score"), rows)


def matches_tsv(candidates: tuple[Candidate, ...]) -> bytes:
    rows: list[dict[str, object]] = []
    for candidate in candidates:
        for match in sorted(candidate.matches, key=lambda item: item.motif_id):
            rows.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "motif_id": match.motif_id,
                    "start": match.start,
                    "end": match.end,
                    "strand": match.strand,
                    "matched_sequence": match.matched_sequence,
                    "raw_score": format(match.raw_score, ".17g"),
                    "normalized_score": format(match.normalized_score, ".17g"),
                }
            )
    return _tsv_bytes(
        (
            "candidate_id",
            "motif_id",
            "start",
            "end",
            "strand",
            "matched_sequence",
            "raw_score",
            "normalized_score",
        ),
        rows,
    )


def candidates_fasta(candidates: tuple[Candidate, ...]) -> bytes:
    return "".join(
        f">{candidate.candidate_id} rank={candidate.rank} "
        f"balance_score={candidate.balance_score:.17g}\n{candidate.sequence}\n"
        for candidate in candidates
    ).encode()


def base_artifact_payloads(
    spec: DesignSpec,
    candidates: tuple[Candidate, ...],
) -> dict[str, bytes]:
    return {
        "design.json": _json_bytes(_design_payload(spec)),
        "motifs.json": _json_bytes(_motifs_payload(spec)),
        "candidates.tsv": candidates_tsv(candidates),
        "matches.tsv": matches_tsv(candidates),
        "candidates.fasta": candidates_fasta(candidates),
    }


def artifact_records(payloads: dict[str, bytes]) -> tuple[ArtifactDigest, ...]:
    for path, payload in payloads.items():
        if len(payload) > MAX_BUNDLE_ARTIFACT_BYTES:
            raise ArtifactError(
                f"Artifact '{path}' exceeds the {MAX_BUNDLE_ARTIFACT_BYTES}-byte bundle byte limit."
            )
    return tuple(
        ArtifactDigest(path=path, sha256=_digest(payload), bytes=len(payload))
        for path, payload in sorted(payloads.items())
    )


def _manifest_payload(manifest: RunManifest) -> dict[str, object]:
    payload = manifest.model_dump(mode="json", exclude={"artifacts"})
    payload["artifacts"] = {
        artifact.path: {"sha256": artifact.sha256, "bytes": artifact.bytes}
        for artifact in manifest.artifacts
    }
    return payload


def _parse_manifest(payload: dict[str, Any]) -> RunManifest:
    artifacts_payload = payload.pop("artifacts", None)
    if not isinstance(artifacts_payload, dict):
        raise ArtifactError("manifest artifacts must be a path-keyed object")
    artifacts = []
    for path, record in sorted(artifacts_payload.items()):
        if not isinstance(record, dict):
            raise ArtifactError(f"manifest artifact record for '{path}' is malformed")
        artifacts.append(ArtifactDigest(path=path, **record))
    return RunManifest.model_validate({**payload, "artifacts": tuple(artifacts)})


def manifest_bytes(manifest: RunManifest) -> bytes:
    return _json_bytes(_manifest_payload(manifest))


@dataclass(frozen=True, slots=True)
class BundleSnapshot:
    """One descriptor-bound set of bundle bytes and its parsed portfolio."""

    portfolio: PortfolioRecord
    members: tuple[tuple[str, bytes], ...]

    def payload(self, path: str) -> bytes:
        for member_path, payload in self.members:
            if member_path == path:
                return payload
        raise ArtifactError(f"bundle snapshot does not contain '{path}'")


def _json_object(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ArtifactError(f"unable to read canonical JSON '{label}': {exc}") from exc
    if not isinstance(payload, dict):
        raise ArtifactError(f"canonical JSON '{label}' must contain an object")
    return payload


def _read_spec(members: dict[str, bytes]) -> DesignSpec:
    motif_collection = _json_object(members["motifs.json"], label="motifs.json")
    raw_motifs = motif_collection.get("motifs")
    if motif_collection.get("schema_version") != "motif-collection/v1" or not isinstance(
        raw_motifs, list
    ):
        raise ArtifactError("motifs.json does not satisfy motif-collection/v1")
    motifs: list[MotifModel] = []
    for raw in raw_motifs:
        if not isinstance(raw, dict):
            raise ArtifactError("motifs.json contains a malformed motif")
        expected_digest = raw.pop("model_digest", None)
        raw.pop("width", None)
        motif = MotifModel.model_validate(raw)
        if motif.model_digest != expected_digest:
            raise ArtifactError(f"model digest mismatch for motif '{motif.motif_id}'")
        motifs.append(motif)
    design_payload = _json_object(members["design.json"], label="design.json")
    references = design_payload.pop("motifs", None)
    if not isinstance(references, list):
        raise ArtifactError("design.json motifs must be a list")
    expected = [
        {"motif_id": motif.motif_id, "model_digest": motif.model_digest} for motif in motifs
    ]
    if references != expected:
        raise ArtifactError("design.json motif references do not match motifs.json")
    return DesignSpec.model_validate({**design_payload, "motifs": tuple(motifs)})


def _read_candidates(members: dict[str, bytes], spec: DesignSpec) -> tuple[Candidate, ...]:
    matches_by_candidate: dict[str, list[MotifMatch]] = defaultdict(list)
    expected_match_rows = spec.count * len(spec.motifs)
    if spec.count > MAX_BUNDLE_ROWS or expected_match_rows > MAX_BUNDLE_ROWS:
        raise ArtifactError("design exceeds the canonical table row limit")
    try:
        match_stream = io.StringIO(members["matches.tsv"].decode("utf-8"), newline="")
        for row_number, row in enumerate(csv.DictReader(match_stream, delimiter="\t"), start=1):
            if row_number > expected_match_rows:
                raise ArtifactError("matches.tsv exceeds its semantic row limit")
            candidate_id = row.pop("candidate_id")
            matches_by_candidate[candidate_id].append(
                MotifMatch(
                    motif_id=row["motif_id"],
                    start=int(row["start"]),
                    end=int(row["end"]),
                    strand=cast(Literal["+", "-"], row["strand"]),
                    matched_sequence=row["matched_sequence"],
                    raw_score=float(row["raw_score"]),
                    normalized_score=float(row["normalized_score"]),
                )
            )
        candidates: list[Candidate] = []
        candidate_stream = io.StringIO(members["candidates.tsv"].decode("utf-8"), newline="")
        for row_number, row in enumerate(csv.DictReader(candidate_stream, delimiter="\t"), start=1):
            if row_number > spec.count:
                raise ArtifactError("candidates.tsv exceeds its semantic row limit")
            candidate_id = row["candidate_id"]
            sequence = row["sequence"]
            if int(row["length"]) != len(sequence):
                raise ArtifactError(f"candidate length mismatch for '{candidate_id}'")
            candidates.append(
                Candidate(
                    candidate_id=candidate_id,
                    rank=int(row["rank"]),
                    sequence=sequence,
                    balance_score=float(row["balance_score"]),
                    matches=tuple(
                        sorted(
                            matches_by_candidate.pop(candidate_id, []),
                            key=lambda match: match.motif_id,
                        )
                    ),
                )
            )
    except (UnicodeDecodeError, csv.Error, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ArtifactError):
            raise
        raise ArtifactError(f"unable to read canonical tables: {exc}") from exc
    if matches_by_candidate:
        raise ArtifactError("matches.tsv contains unresolved candidate identifiers")
    if len(candidates) != spec.count:
        raise ArtifactError("candidate row count does not equal design count")
    return tuple(candidates)


def _read_snapshot_member(
    directory_descriptor: int,
    path: str,
    *,
    limit: int,
    expected_bytes: int | None = None,
) -> bytes:
    descriptor: int | None = None
    try:
        before = os.stat(path, dir_fd=directory_descriptor, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise ArtifactError(f"bundle snapshot contains unsafe member '{path}'")
        if before.st_size > limit:
            raise ArtifactError(f"bundle member '{path}' exceeds the {limit}-byte limit")
        if expected_bytes is not None and before.st_size != expected_bytes:
            raise ArtifactError(f"artifact digest or size mismatch for '{path}'")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, dir_fd=directory_descriptor)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
            or opened.st_size != before.st_size
        ):
            raise ArtifactError(f"bundle member '{path}' changed during bundle snapshot")
        read_limit = (expected_bytes if expected_bytes is not None else limit) + 1
        chunks: list[bytes] = []
        remaining = read_limit
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        after = os.fstat(descriptor)
        if (
            (after.st_dev, after.st_ino) != (opened.st_dev, opened.st_ino)
            or after.st_size != opened.st_size
            or len(payload) != opened.st_size
        ):
            raise ArtifactError(f"bundle member '{path}' changed during bundle snapshot")
        return payload
    except OSError as exc:
        raise ArtifactError(
            f"bundle member '{path}' changed during bundle snapshot or is unsafe"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def read_bundle_snapshot(directory: str | Path) -> BundleSnapshot:
    """Read and validate every member once through a pinned directory descriptor."""

    root = Path(directory)
    directory_descriptor: int | None = None
    try:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_DIRECTORY", 0)
        )
        directory_descriptor = os.open(root, flags)
        opened_root = os.fstat(directory_descriptor)
        if not stat.S_ISDIR(opened_root.st_mode):
            raise ArtifactError(f"bundle directory does not exist or is unsafe: {root}")
        files = set(os.listdir(directory_descriptor))
        for path in files:
            if not path or "/" in path or "\\" in path:
                raise ArtifactError("bundle inventory contains an unsafe member name")
            member_stat = os.stat(
                path,
                dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
            if not stat.S_ISREG(member_stat.st_mode):
                raise ArtifactError(f"bundle contains unsafe non-file entry '{path}'")
    except OSError as exc:
        if directory_descriptor is not None:
            os.close(directory_descriptor)
        raise ArtifactError(f"bundle directory does not exist or is unsafe: {root}") from exc
    except ArtifactError:
        if directory_descriptor is not None:
            os.close(directory_descriptor)
        raise
    assert directory_descriptor is not None
    try:
        if "manifest.json" not in files:
            raise ArtifactError("bundle inventory mismatch; missing=['manifest.json'], extra=[]")
        canonical_manifest = _read_snapshot_member(
            directory_descriptor,
            "manifest.json",
            limit=MAX_INPUT_BYTES,
        )
        manifest = _parse_manifest(_json_object(canonical_manifest, label="manifest.json"))
        expected_files = _schema_files(manifest)
        if files != expected_files:
            missing = sorted(expected_files - files)
            extra = sorted(files - expected_files)
            raise ArtifactError(f"bundle inventory mismatch; missing={missing}, extra={extra}")
        declared = {artifact.path: artifact for artifact in manifest.artifacts}
        if set(declared) != expected_files - {"manifest.json"}:
            raise ArtifactError("manifest artifact inventory is incomplete")
        members = {"manifest.json": canonical_manifest}
        for path, artifact in declared.items():
            member_limit = (
                MAX_INPUT_BYTES
                if path in {"design.json", "motifs.json"}
                else MAX_BUNDLE_ARTIFACT_BYTES
            )
            if artifact.bytes > member_limit:
                raise ArtifactError(f"bundle member '{path}' exceeds the {member_limit}-byte limit")
            payload = _read_snapshot_member(
                directory_descriptor,
                path,
                limit=member_limit,
                expected_bytes=artifact.bytes,
            )
            if _digest(payload) != artifact.sha256:
                raise ArtifactError(f"artifact digest mismatch for '{path}'")
            members[path] = payload
        if set(os.listdir(directory_descriptor)) != files:
            raise ArtifactError("bundle inventory changed during bundle snapshot")
        closed_root = os.fstat(directory_descriptor)
        if (closed_root.st_dev, closed_root.st_ino) != (opened_root.st_dev, opened_root.st_ino):
            raise ArtifactError("bundle directory changed during bundle snapshot")
    finally:
        os.close(directory_descriptor)

    spec = _read_spec(members)
    candidates = _read_candidates(members, spec)
    expected_payloads = base_artifact_payloads(spec, candidates)
    for path, payload in expected_payloads.items():
        if payload != members[path]:
            raise ArtifactError(f"artifact semantic replay mismatch for '{path}'")
    if bundle_id(manifest) != manifest.bundle_id:
        raise ArtifactError("bundle identity does not match its artifact digests")
    if canonical_manifest != manifest_bytes(manifest):
        raise ArtifactError("manifest does not use the canonical encoding")
    portfolio = PortfolioRecord(
        problem_id=manifest.problem_id,
        run_id=manifest.run_id,
        spec=spec,
        candidates=candidates,
        manifest=manifest,
    )
    return BundleSnapshot(portfolio=portfolio, members=tuple(sorted(members.items())))


def read_portfolio_record(directory: str | Path) -> PortfolioRecord:
    return read_bundle_snapshot(directory).portfolio


def verify_portfolio_record(portfolio: PortfolioRecord) -> None:
    """Replay identities, search provenance, and every published candidate score."""

    problem = compile_design(portfolio.spec)
    if problem.problem_id != portfolio.manifest.problem_id:
        raise ArtifactError("scientific replay found a problem identity mismatch")
    expected_run = build_run_id(
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

    seen_ids: set[str] = set()
    for candidate in portfolio.candidates:
        if candidate.candidate_id in seen_ids:
            raise ArtifactError("scientific replay found duplicate candidate identifiers")
        seen_ids.add(candidate.candidate_id)
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


def read_verified_portfolio_snapshot(
    directory: str | Path,
    *,
    expected_bundle_id: str | None = None,
) -> tuple[PortfolioRecord, BundleSnapshot]:
    """Read one descriptor-bound bundle snapshot and replay its scientific records."""

    snapshot = read_bundle_snapshot(directory)
    portfolio = snapshot.portfolio
    if expected_bundle_id is not None and portfolio.manifest.bundle_id != expected_bundle_id:
        raise ArtifactError("bundle identity does not match the externally expected identity")
    verify_portfolio_record(portfolio)
    return portfolio, snapshot


def read_verified_portfolio(
    directory: str | Path,
    *,
    expected_bundle_id: str | None = None,
) -> PortfolioRecord:
    portfolio, _snapshot = read_verified_portfolio_snapshot(
        directory,
        expected_bundle_id=expected_bundle_id,
    )
    return portfolio


def verify_bundle(
    directory: str | Path,
    *,
    expected_bundle_id: str | None = None,
) -> str:
    return read_verified_portfolio(
        directory,
        expected_bundle_id=expected_bundle_id,
    ).manifest.bundle_id


def bundle_id(manifest: RunManifest) -> str:
    """Bind every canonical manifest field except the identity being computed."""
    payload = _manifest_payload(manifest)
    payload.pop("bundle_id")
    return f"bundle-{_digest(_json_bytes(payload))[:24]}"


def write_bundle(
    portfolio: PortfolioRecord,
    output: Path,
    payloads: dict[str, bytes],
) -> Path:
    if output.exists() or output.is_symlink():
        raise ArtifactError(f"output directory already exists or is unsafe: '{output.name}'")
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ArtifactError("unable to create the bundle publication directory") from exc
    if portfolio.manifest.schema_version != "run-manifest/v3":
        raise ArtifactError("new bundle publication requires run-manifest/v3")
    if set(payloads) != _V3_FILES - {"manifest.json"}:
        raise ArtifactError("bundle payload inventory is incomplete")
    records = artifact_records(payloads)
    if records != portfolio.manifest.artifacts:
        raise ArtifactError("portfolio artifact digests do not match its semantic contents")
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    try:
        for path, payload in payloads.items():
            (temporary / path).write_bytes(payload)
        (temporary / "manifest.json").write_bytes(manifest_bytes(portfolio.manifest))
        replay = read_portfolio_record(temporary)
        if replay.model_dump(mode="python") != portfolio.model_dump(mode="python"):
            raise ArtifactError("bundle round-trip validation changed portfolio semantics")
        if output.exists() or output.is_symlink():
            raise ArtifactError(f"output directory already exists or is unsafe: '{output.name}'")
        os.rename(temporary, output)
    except OSError as exc:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise ArtifactError("unable to publish the canonical bundle") from exc
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return output
