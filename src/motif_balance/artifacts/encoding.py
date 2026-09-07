"""Canonical artifact bytes and content identities."""

from __future__ import annotations

import csv
import hashlib
import io
import json

from motif_balance.constants import (
    MAX_BUNDLE_ARTIFACT_BYTES,
    MAX_INPUT_BYTES,
    MAX_RUN_MANIFEST_BYTES,
)
from motif_balance.errors import ArtifactError
from motif_balance.model import (
    ArtifactDigest,
    Candidate,
    DesignSpec,
    RunManifest,
)


def _json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _design_payload(spec: DesignSpec) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": spec.schema_version,
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
    if spec.schema_version == "design-spec/v3":
        payload["specifications"] = [
            {
                "motif_id": item.motif.motif_id,
                "model_digest": item.motif.model_digest,
                "direction": item.direction,
            }
            for item in spec.specifications
        ]
    else:
        payload["motifs"] = [
            {"motif_id": motif.motif_id, "model_digest": motif.model_digest}
            for motif in spec.motifs
        ]
    if spec.avoiders:
        payload["avoiders"] = [
            {
                "motif_id": item.motif.motif_id,
                "model_digest": item.motif.model_digest,
                "score_ceiling": item.score_ceiling,
            }
            for item in spec.avoiders
        ]
    return payload


def _motifs_payload(spec: DesignSpec) -> dict[str, object]:
    motifs = []
    all_motifs = (*spec.scored_motifs, *(item.motif for item in spec.avoiders))
    for motif in sorted(all_motifs, key=lambda item: item.motif_id):
        payload = motif.model_dump(mode="json")
        payload["width"] = motif.width
        payload["model_digest"] = motif.model_digest
        motifs.append(payload)
    collection_version = (
        "motif-collection/v1" if spec.schema_version == "design-spec/v1" else "motif-collection/v2"
    )
    return {"schema_version": collection_version, "motifs": motifs}


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


def matches_tsv(spec: DesignSpec, candidates: tuple[Candidate, ...]) -> bytes:
    rows: list[dict[str, object]] = []
    ceilings = {item.motif.motif_id: item.score_ceiling for item in spec.avoiders}
    for candidate in candidates:
        for match in sorted(candidate.matches, key=lambda item: item.motif_id):
            row: dict[str, object] = {
                "candidate_id": candidate.candidate_id,
                "motif_id": match.motif_id,
                "start": match.start,
                "end": match.end,
                "strand": match.strand,
                "matched_sequence": match.matched_sequence,
                "raw_score": format(match.raw_score, ".17g"),
                "normalized_score": format(match.normalized_score, ".17g"),
            }
            if spec.schema_version == "design-spec/v3":
                row = {
                    **row,
                    "role": "specification",
                    "direction": match.spec_direction,
                    "spec_satisfaction": format(match.spec_satisfaction, ".17g"),
                }
            elif spec.schema_version == "design-spec/v2":
                row = {**row, "role": "target", "score_ceiling": ""}
            rows.append(row)
        if spec.schema_version == "design-spec/v2":
            for match in sorted(candidate.avoidance_matches, key=lambda item: item.motif_id):
                rows.append(
                    {
                        "candidate_id": candidate.candidate_id,
                        "role": "avoider",
                        "motif_id": match.motif_id,
                        "score_ceiling": format(ceilings[match.motif_id], ".17g"),
                        "start": match.start,
                        "end": match.end,
                        "strand": match.strand,
                        "matched_sequence": match.matched_sequence,
                        "raw_score": format(match.raw_score, ".17g"),
                        "normalized_score": format(match.normalized_score, ".17g"),
                    }
                )
    fields = (
        (
            "candidate_id",
            "role",
            "direction",
            "motif_id",
            "start",
            "end",
            "strand",
            "matched_sequence",
            "raw_score",
            "normalized_score",
            "spec_satisfaction",
        )
        if spec.schema_version == "design-spec/v3"
        else (
            "candidate_id",
            "role",
            "motif_id",
            "score_ceiling",
            "start",
            "end",
            "strand",
            "matched_sequence",
            "raw_score",
            "normalized_score",
        )
        if spec.schema_version == "design-spec/v2"
        else (
            "candidate_id",
            "motif_id",
            "start",
            "end",
            "strand",
            "matched_sequence",
            "raw_score",
            "normalized_score",
        )
    )
    return _tsv_bytes(fields, rows)


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
        "matches.tsv": matches_tsv(spec, candidates),
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


def manifest_bytes(manifest: RunManifest) -> bytes:
    payload = _json_bytes(_manifest_payload(manifest))
    limit = (
        MAX_RUN_MANIFEST_BYTES if manifest.schema_version == "run-manifest/v6" else MAX_INPUT_BYTES
    )
    if len(payload) > limit:
        raise ArtifactError(f"bundle member 'manifest.json' exceeds the {limit}-byte limit")
    return payload


def bundle_id(manifest: RunManifest) -> str:
    """Bind every canonical manifest field except the identity being computed."""
    payload = _manifest_payload(manifest)
    payload.pop("bundle_id")
    return f"bundle-{_digest(_json_bytes(payload))[:24]}"
