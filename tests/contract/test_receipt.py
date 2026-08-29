from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from motif_balance import DesignSpec, design
from motif_balance.receipt import build_execution_receipt, receipt_bytes


def test_execution_receipt_binds_the_actual_execution_interval_and_release(
    pairwise_spec: DesignSpec,
) -> None:
    portfolio = design(pairwise_spec)
    receipt = build_execution_receipt(
        portfolio,
        manifest_payload=b"canonical manifest\n",
        producer_revision="a" * 40,
        release_artifact_name="motif_balance-0.4.0a1-py3-none-any.whl",
        release_artifact_sha256="b" * 64,
        runtime_package_tree_sha256="d" * 64,
        normalized_design_sha256="c" * 64,
        started_at=datetime(2026, 8, 26, 12, 30, tzinfo=UTC),
        finished_at=datetime(2026, 8, 26, 12, 31, tzinfo=UTC),
    )

    assert receipt.schema_version == "motif-balance.execution-receipt/v1"
    assert receipt.operation == "design"
    assert receipt.execution_status == "completed"
    assert receipt.bundle_id == portfolio.manifest.bundle_id
    assert receipt.run_id == portfolio.run_id
    assert receipt.producer_revision == "a" * 40
    assert receipt.release_artifact_sha256 == "b" * 64
    assert receipt.normalized_design_sha256 == "c" * 64
    assert receipt.runtime_package_tree_sha256 == "d" * 64
    assert receipt.started_at_utc == "2026-08-26T12:30:00Z"
    assert receipt.finished_at_utc == "2026-08-26T12:31:00Z"
    assert [item.name for item in receipt.dependencies] == [
        "numpy",
        "pydantic",
        "pyyaml",
        "typer",
    ]
    payload = receipt_bytes(receipt)
    assert payload.endswith(b"\n")
    assert hashlib.sha256(payload).hexdigest()
