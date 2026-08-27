from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from motif_balance.model import ArtifactDigest, PortfolioRecord

from .model import ExecutionInspection


@dataclass(frozen=True, slots=True)
class VerifiedResultSource:
    """Descriptor-bound snapshot consumed once by the pure review projector."""

    portfolio: PortfolioRecord
    canonical_manifest: bytes
    artifacts: tuple[tuple[ArtifactDigest, bytes], ...]
    subject_kind: Literal["bundle", "execution"]
    integrity_state: Literal["self_consistent", "externally_verified", "readable_untrusted"]
    trust_basis: Literal[
        "self_consistent",
        "external_bundle_id",
        "external_execution_identities",
    ]
    checked_identities: tuple[str, ...]
    execution: ExecutionInspection | None = None
