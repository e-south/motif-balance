"""Strict reconstruction of design and candidate records from bytes."""

from __future__ import annotations

import csv
import io
import json
import math
from collections import defaultdict
from typing import Any, Literal, cast

from motif_balance.constants import (
    MAX_BUNDLE_ROWS,
)
from motif_balance.errors import ArtifactError
from motif_balance.model import (
    ArtifactDigest,
    Candidate,
    DesignSpec,
    MotifMatch,
    MotifModel,
    RunManifest,
)


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
    collection_version = motif_collection.get("schema_version")
    if collection_version not in {"motif-collection/v1", "motif-collection/v2"} or not isinstance(
        raw_motifs, list
    ):
        raise ArtifactError("motifs.json does not satisfy a supported motif collection schema")
    motifs: dict[str, MotifModel] = {}
    for raw in raw_motifs:
        if not isinstance(raw, dict):
            raise ArtifactError("motifs.json contains a malformed motif")
        expected_digest = raw.pop("model_digest", None)
        raw.pop("width", None)
        motif = MotifModel.model_validate(raw)
        if motif.model_digest != expected_digest:
            raise ArtifactError(f"model digest mismatch for motif '{motif.motif_id}'")
        if motif.motif_id in motifs:
            raise ArtifactError("motifs.json contains duplicate motif identifiers")
        motifs[motif.motif_id] = motif
    design_payload = _json_object(members["design.json"], label="design.json")
    schema_version = design_payload.get("schema_version")
    references = design_payload.pop("motifs", None)
    specification_references = design_payload.pop("specifications", None)
    target_models: tuple[MotifModel, ...] = ()
    specifications: tuple[dict[str, object], ...] = ()
    referenced_ids: set[str] = set()
    if schema_version == "design-spec/v3":
        if references is not None:
            raise ArtifactError("design-spec/v3 cannot contain legacy motif references")
        if not isinstance(specification_references, list) or not specification_references:
            raise ArtifactError("design.json specifications must be a nonempty list")
        parsed_specifications: list[dict[str, object]] = []
        expected_specifications: list[dict[str, object]] = []
        for item in specification_references:
            if not isinstance(item, dict):
                raise ArtifactError("design.json contains a malformed motif specification")
            motif_id = item.get("motif_id")
            direction = item.get("direction")
            if not isinstance(motif_id, str) or motif_id not in motifs:
                raise ArtifactError("design.json specification does not reference motifs.json")
            if direction not in {"seek", "avoid"}:
                raise ArtifactError("design.json specification has an unknown direction")
            expected_specifications.append(
                {
                    "motif_id": motif_id,
                    "model_digest": motifs[motif_id].model_digest,
                    "direction": direction,
                }
            )
            parsed_specifications.append({"motif": motifs[motif_id], "direction": direction})
            referenced_ids.add(motif_id)
        if specification_references != expected_specifications:
            raise ArtifactError("design.json specifications do not match motifs.json")
        specifications = tuple(parsed_specifications)
    else:
        if specification_references is not None:
            raise ArtifactError("legacy design schema cannot contain specifications")
        if not isinstance(references, list):
            raise ArtifactError("design.json motifs must be a list")
        expected: list[dict[str, str]] = []
        for item in references:
            if not isinstance(item, dict):
                raise ArtifactError("design.json contains a malformed target motif reference")
            motif_id = item.get("motif_id")
            if not isinstance(motif_id, str) or motif_id not in motifs:
                raise ArtifactError("design.json target motif does not reference motifs.json")
            expected.append({"motif_id": motif_id, "model_digest": motifs[motif_id].model_digest})
            referenced_ids.add(motif_id)
        if references != expected:
            raise ArtifactError("design.json motif references do not match motifs.json")
        target_models = tuple(motifs[item["motif_id"]] for item in references)
    avoiders_payload = design_payload.pop("avoiders", [])
    avoiders: list[dict[str, object]] = []
    referenced_avoider_ids: set[str] = set()
    if schema_version == "design-spec/v2":
        if not isinstance(avoiders_payload, list):
            raise ArtifactError("design.json avoiders must be a list")
        for item in avoiders_payload:
            if not isinstance(item, dict):
                raise ArtifactError("design.json contains a malformed avoider")
            motif_id = item.get("motif_id")
            if not isinstance(motif_id, str) or motif_id not in motifs:
                raise ArtifactError("design.json avoider does not reference motifs.json")
            if item.get("model_digest") != motifs[motif_id].model_digest:
                raise ArtifactError("design.json avoider digest does not match motifs.json")
            avoiders.append({"motif": motifs[motif_id], "score_ceiling": item.get("score_ceiling")})
            referenced_avoider_ids.add(motif_id)
        referenced_ids |= referenced_avoider_ids
        if referenced_ids != set(motifs):
            raise ArtifactError("motifs.json contains unreferenced motif models")
    elif referenced_ids != set(motifs):
        raise ArtifactError("motifs.json contains unreferenced motif models")
    spec = DesignSpec.model_validate(
        {
            **design_payload,
            "motifs": target_models,
            "specifications": specifications,
            "avoiders": tuple(avoiders),
        }
    )
    expected_collection = (
        "motif-collection/v1" if spec.schema_version == "design-spec/v1" else "motif-collection/v2"
    )
    if collection_version != expected_collection:
        raise ArtifactError("motif collection and design schema versions do not agree")
    return spec


def _read_candidates(members: dict[str, bytes], spec: DesignSpec) -> tuple[Candidate, ...]:
    matches_by_candidate: dict[str, list[MotifMatch]] = defaultdict(list)
    avoidance_by_candidate: dict[str, list[MotifMatch]] = defaultdict(list)
    expected_match_rows = spec.count * (len(spec.scored_motifs) + len(spec.avoiders))
    if spec.count > MAX_BUNDLE_ROWS or expected_match_rows > MAX_BUNDLE_ROWS:
        raise ArtifactError("design exceeds the canonical table row limit")
    try:
        match_stream = io.StringIO(members["matches.tsv"].decode("utf-8"), newline="")
        for row_number, row in enumerate(csv.DictReader(match_stream, delimiter="\t"), start=1):
            if row_number > expected_match_rows:
                raise ArtifactError("matches.tsv exceeds its semantic row limit")
            candidate_id = row.pop("candidate_id")
            role = row.pop("role", "target")
            ceiling = row.pop("score_ceiling", "")
            direction = row.pop("direction", "")
            satisfaction = row.pop("spec_satisfaction", "")
            if spec.schema_version == "design-spec/v3":
                if role != "specification":
                    raise ArtifactError("directional matches must use the specification role")
                declared_directions = {
                    item.motif.motif_id: item.direction for item in spec.specifications
                }
                if direction != declared_directions.get(row["motif_id"]):
                    raise ArtifactError("match direction does not agree with design.json")
                if ceiling or not satisfaction:
                    raise ArtifactError("directional match has malformed satisfaction evidence")
                destination = matches_by_candidate
            else:
                destination = matches_by_candidate if role == "target" else avoidance_by_candidate
                if role not in {"target", "avoider"}:
                    raise ArtifactError("matches.tsv contains an unknown motif role")
            if role == "target" and ceiling:
                raise ArtifactError("target match cannot declare an avoider ceiling")
            expected_ceiling = {
                item.motif.motif_id: item.score_ceiling for item in spec.avoiders
            }.get(row["motif_id"])
            if role == "avoider" and (
                expected_ceiling is None or float(ceiling) != expected_ceiling
            ):
                raise ArtifactError("avoider match ceiling does not match design.json")
            destination[candidate_id].append(
                MotifMatch(
                    motif_id=row["motif_id"],
                    start=int(row["start"]),
                    end=int(row["end"]),
                    strand=cast(Literal["+", "-"], row["strand"]),
                    matched_sequence=row["matched_sequence"],
                    raw_score=float(row["raw_score"]),
                    normalized_score=float(row["normalized_score"]),
                    spec_direction=(
                        cast(Literal["seek", "avoid"], direction)
                        if spec.schema_version == "design-spec/v3"
                        else None
                    ),
                    spec_satisfaction=(
                        float(satisfaction) if spec.schema_version == "design-spec/v3" else None
                    ),
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
            avoider_matches = tuple(
                sorted(
                    avoidance_by_candidate.pop(candidate_id, []),
                    key=lambda match: match.motif_id,
                )
            )
            ceilings = {item.motif.motif_id: item.score_ceiling for item in spec.avoiders}
            max_excess = max(
                (
                    max(0.0, match.normalized_score - ceilings[match.motif_id])
                    for match in avoider_matches
                ),
                default=0.0,
            )
            total_excess = math.fsum(
                max(0.0, match.normalized_score - ceilings[match.motif_id])
                for match in avoider_matches
            )
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
                    avoidance_matches=avoider_matches,
                    constraint_status="feasible" if max_excess <= 1.0e-12 else "infeasible",
                    max_avoidance_excess=max_excess,
                    total_avoidance_excess=total_excess,
                )
            )
    except (UnicodeDecodeError, csv.Error, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ArtifactError):
            raise
        raise ArtifactError(f"unable to read canonical tables: {exc}") from exc
    if matches_by_candidate or avoidance_by_candidate:
        raise ArtifactError("matches.tsv contains unresolved candidate identifiers")
    if len(candidates) != spec.count:
        raise ArtifactError("candidate row count does not equal design count")
    return tuple(candidates)
