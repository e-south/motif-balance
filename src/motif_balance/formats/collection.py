"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/formats/collection.py

Read and serialize the inputs and selected members of a saved collection.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from pathlib import Path

from motif_balance.constants import MAX_RUN_MANIFEST_BYTES
from motif_balance.model.alternatives import ArchitectureRanking, CollectionReport

from .structured import load_json_unique, read_bounded_regular_file


def collection_json(
    ranking: ArchitectureRanking, *, count: int, source_id: str, anchored: bool
) -> str:
    return (
        CollectionReport(
            source_bundle_id=source_id,
            source_verification="external_bundle_id" if anchored else "self_consistent",
            ranking=ranking,
            collection=ranking.select_up_to(count),
        ).model_dump_json(indent=2)
        + "\n"
    )


def read_collection(path: Path) -> CollectionReport:
    """Check report structure and selection; callers rescore the chosen parent."""
    raw = read_bounded_regular_file(path, max_bytes=MAX_RUN_MANIFEST_BYTES)
    return CollectionReport.model_validate(load_json_unique(raw))
