from __future__ import annotations

import hashlib
import json
from importlib import resources

from motif_balance.constants import PACKAGE_VERSION
from motif_balance.errors import ArtifactError

from .model import InspectionCandidate, ResultInspection
from .render import render_candidate_svg

CANDIDATE_SVG_RENDERER_IDENTITY = "motif-balance.candidate-information-logo-svg/v1"
_RENDERER_MODULES = (
    "candidate.py",
    "candidate_layout.py",
    "candidate_projection.py",
    "candidate_sections.py",
    "candidate_support.py",
    "information_logo.py",
    "svg_primitives.py",
)


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _renderer_implementation_sha256() -> str:
    digest = hashlib.sha256()
    package = resources.files("motif_balance.inspection.render")
    for name in _RENDERER_MODULES:
        payload = package.joinpath(name).read_bytes()
        encoded_name = name.encode("ascii")
        digest.update(len(encoded_name).to_bytes(2, "big"))
        digest.update(encoded_name)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _candidate(inspection: ResultInspection, rank: int) -> InspectionCandidate:
    candidate = next(
        (item for item in inspection.portfolio.candidates if item.rank == rank),
        None,
    )
    if candidate is None:
        raise ArtifactError(f"candidate rank {rank} is not present in this result")
    return candidate


def _match_projection(
    candidate: InspectionCandidate,
    *,
    avoider: bool,
) -> tuple[dict[str, object], ...]:
    matches = candidate.avoidance_matches if avoider else candidate.matches
    role = "avoider" if avoider else "target"
    return tuple(
        {
            "role": role,
            **match.model_dump(mode="json"),
        }
        for match in matches
    )


def render_candidate_svg_receipt(
    inspection: ResultInspection,
    *,
    candidate_rank: int,
    svg: bytes,
) -> bytes:
    """Bind one emitted candidate SVG to its verified review projection and renderer."""

    canonical_svg = render_candidate_svg(inspection, candidate_rank=candidate_rank)
    if svg != canonical_svg:
        raise ArtifactError(
            "candidate SVG receipt requires the canonical candidate renderer output"
        )
    candidate = _candidate(inspection, candidate_rank)
    target_projection = _match_projection(candidate, avoider=False)
    avoider_projection = _match_projection(candidate, avoider=True)
    execution = inspection.execution
    payload = {
        "schema_version": "motif-balance.candidate-svg-receipt/v1",
        "bundle_id": inspection.run.bundle_id,
        "problem_id": inspection.problem.problem_id,
        "candidate": {
            "candidate_id": candidate.candidate_id,
            "rank": candidate.rank,
            "sequence": candidate.sequence,
            "balance_score": candidate.balance_score,
            "limiting_motif_ids": candidate.limiting_motif_ids,
            "target_match_projection_sha256": _digest(target_projection),
            "avoider_match_projection_sha256": _digest(avoider_projection),
        },
        "svg_sha256": hashlib.sha256(svg).hexdigest(),
        "renderer_identity": CANDIDATE_SVG_RENDERER_IDENTITY,
        "renderer_implementation_sha256": _renderer_implementation_sha256(),
        "renderer_package_version": PACKAGE_VERSION,
        "result_package_version": inspection.run.package_version,
        "subject": {
            "kind": inspection.subject_kind,
            "integrity_state": inspection.integrity.state,
            "trust_basis": inspection.integrity.trust_basis,
            "checked_identities": inspection.integrity.checked_identities,
        },
        "execution_release": (
            {
                "workspace_id": execution.workspace_id,
                "producer_revision": execution.producer_revision,
                "release_artifact_name": execution.release_artifact_name,
                "release_artifact_sha256": execution.release_artifact_sha256,
                "receipt_sha256": execution.receipt_sha256,
            }
            if execution is not None
            else None
        ),
    }
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()
