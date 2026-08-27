from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal, cast

from motif_balance.constants import (
    MAX_BUNDLE_ARTIFACT_BYTES,
    MAX_BUNDLE_ROWS,
    MAX_INPUT_BYTES,
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

_CANONICAL_FILES = {
    "design.json",
    "motifs.json",
    "candidates.tsv",
    "matches.tsv",
    "manifest.json",
}
_DERIVED_FILES = {"candidates.fasta", "report.html"}
_ALL_FILES = _CANONICAL_FILES | _DERIVED_FILES


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


def _safe_files(directory: Path) -> set[str]:
    names: set[str] = set()
    for entry in directory.iterdir():
        if entry.is_symlink() or not entry.is_file():
            raise ArtifactError(f"bundle contains unsafe non-file entry '{entry.name}'")
        names.add(entry.name)
    return names


def _read_bounded_bytes(path: Path, *, limit: int, label: str) -> bytes:
    try:
        if path.stat().st_size > limit:
            raise ArtifactError(f"{label} '{path.name}' exceeds the {limit}-byte limit")
        raw = path.read_bytes()
        if len(raw) > limit:
            raise ArtifactError(f"{label} '{path.name}' exceeds the {limit}-byte limit")
        return raw
    except OSError as exc:
        raise ArtifactError(f"unable to read {label} '{path.name}': {exc}") from exc


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = _read_bounded_bytes(path, limit=MAX_INPUT_BYTES, label="canonical JSON")
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ArtifactError(f"unable to read canonical JSON '{path.name}': {exc}") from exc
    if not isinstance(payload, dict):
        raise ArtifactError(f"canonical JSON '{path.name}' must contain an object")
    return payload


def _read_spec(directory: Path) -> DesignSpec:
    motif_collection = _read_json(directory / "motifs.json")
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
    design_payload = _read_json(directory / "design.json")
    references = design_payload.pop("motifs", None)
    if not isinstance(references, list):
        raise ArtifactError("design.json motifs must be a list")
    expected = [
        {"motif_id": motif.motif_id, "model_digest": motif.model_digest} for motif in motifs
    ]
    if references != expected:
        raise ArtifactError("design.json motif references do not match motifs.json")
    return DesignSpec.model_validate({**design_payload, "motifs": tuple(motifs)})


def _read_candidates(directory: Path, spec: DesignSpec) -> tuple[Candidate, ...]:
    matches_by_candidate: dict[str, list[MotifMatch]] = defaultdict(list)
    expected_match_rows = spec.count * len(spec.motifs)
    if spec.count > MAX_BUNDLE_ROWS or expected_match_rows > MAX_BUNDLE_ROWS:
        raise ArtifactError("design exceeds the canonical table row limit")
    try:
        with (directory / "matches.tsv").open(newline="") as handle:
            for row_number, row in enumerate(csv.DictReader(handle, delimiter="\t"), start=1):
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
        with (directory / "candidates.tsv").open(newline="") as handle:
            for row_number, row in enumerate(csv.DictReader(handle, delimiter="\t"), start=1):
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
    except (OSError, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ArtifactError):
            raise
        raise ArtifactError(f"unable to read canonical tables: {exc}") from exc
    if matches_by_candidate:
        raise ArtifactError("matches.tsv contains unresolved candidate identifiers")
    if len(candidates) != spec.count:
        raise ArtifactError("candidate row count does not equal design count")
    return tuple(candidates)


def verify_bundle_base(directory: str | Path) -> str:
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise ArtifactError(f"bundle directory does not exist or is unsafe: {root}")
    files = _safe_files(root)
    if files != _ALL_FILES:
        missing = sorted(_ALL_FILES - files)
        extra = sorted(files - _ALL_FILES)
        raise ArtifactError(f"bundle inventory mismatch; missing={missing}, extra={extra}")
    manifest = _parse_manifest(_read_json(root / "manifest.json"))
    declared = {artifact.path: artifact for artifact in manifest.artifacts}
    if set(declared) != _ALL_FILES - {"manifest.json"}:
        raise ArtifactError("manifest artifact inventory is incomplete")
    for path, artifact in declared.items():
        if artifact.bytes > MAX_BUNDLE_ARTIFACT_BYTES:
            raise ArtifactError(f"artifact '{path}' exceeds the bundle byte limit")
        payload = _read_bounded_bytes(
            root / path,
            limit=MAX_BUNDLE_ARTIFACT_BYTES,
            label="bundle artifact",
        )
        if len(payload) != artifact.bytes or _digest(payload) != artifact.sha256:
            raise ArtifactError(f"artifact digest mismatch for '{path}'")
    spec = _read_spec(root)
    candidates = _read_candidates(root, spec)
    expected_payloads = base_artifact_payloads(spec, candidates)
    for path, payload in expected_payloads.items():
        if payload != (root / path).read_bytes():
            raise ArtifactError(f"artifact semantic replay mismatch for '{path}'")
    expected_bundle = bundle_id(manifest)
    if expected_bundle != manifest.bundle_id:
        raise ArtifactError("bundle identity does not match its artifact digests")
    actual_manifest = _read_bounded_bytes(
        root / "manifest.json",
        limit=MAX_INPUT_BYTES,
        label="canonical JSON",
    )
    if actual_manifest != manifest_bytes(manifest):
        raise ArtifactError("manifest does not use the canonical encoding")
    return manifest.bundle_id


def read_portfolio_record(directory: str | Path) -> PortfolioRecord:
    root = Path(directory)
    verify_bundle_base(root)
    spec = _read_spec(root)
    candidates = _read_candidates(root, spec)
    manifest = _parse_manifest(_read_json(root / "manifest.json"))
    return PortfolioRecord(
        problem_id=manifest.problem_id,
        run_id=manifest.run_id,
        spec=spec,
        candidates=candidates,
        manifest=manifest,
    )


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
    if set(payloads) != _ALL_FILES - {"manifest.json"}:
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
