"""Contracts for immutable private-prerelease build attestations."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _module() -> ModuleType:
    path = REPO_ROOT / "scripts/release_attestation.py"
    spec = importlib.util.spec_from_file_location("motif_balance_release_attestation", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_attestation_is_canonical_and_binds_exact_artifacts(tmp_path: Path) -> None:
    wheel = tmp_path / "motif_balance-0.2.0a1-py3-none-any.whl"
    sdist = tmp_path / "motif_balance-0.2.0a1.tar.gz"
    wheel.write_bytes(b"wheel-bytes")
    sdist.write_bytes(b"sdist-bytes")
    out = tmp_path / "release-build-attestation.json"

    module = _module()
    digest = module.write_attestation(
        out_path=out,
        wheel_path=wheel,
        sdist_path=sdist,
        repository="e-south/motif-balance",
        revision="a" * 40,
        tree="b" * 40,
        tag="v0.2.0a1",
        version="0.2.0a1",
        lock_sha256="c" * 64,
        builder_kind="maintainer_local",
        python_version="3.12.14",
        uv_version="0.12.3",
        operating_system="Darwin",
        architecture="arm64",
        source_date_epoch=1_700_000_000,
        limitations=[
            "hosted_ci_unavailable_account_billing",
            "independent_rebuild_not_performed",
        ],
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert digest.startswith("sha256:")
    assert out.read_bytes() == (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    assert payload["schema"] == "motif-balance.release-build-attestation/v1"
    assert [artifact["kind"] for artifact in payload["artifacts"]] == ["sdist", "wheel"]
    assert (
        module.verify_attestation(attestation_path=out, wheel_path=wheel, sdist_path=sdist)
        == digest
    )


def test_release_attestation_rejects_substituted_artifact(tmp_path: Path) -> None:
    wheel = tmp_path / "motif_balance-0.2.0a1-py3-none-any.whl"
    sdist = tmp_path / "motif_balance-0.2.0a1.tar.gz"
    wheel.write_bytes(b"wheel-bytes")
    sdist.write_bytes(b"sdist-bytes")
    out = tmp_path / "release-build-attestation.json"
    module = _module()
    module.write_attestation(
        out_path=out,
        wheel_path=wheel,
        sdist_path=sdist,
        repository="e-south/motif-balance",
        revision="a" * 40,
        tree="b" * 40,
        tag="v0.2.0a1",
        version="0.2.0a1",
        lock_sha256="c" * 64,
        builder_kind="maintainer_local",
        python_version="3.12.14",
        uv_version="0.12.3",
        operating_system="Darwin",
        architecture="arm64",
        source_date_epoch=1_700_000_000,
        limitations=["independent_rebuild_not_performed"],
    )
    wheel.write_bytes(b"substituted")

    with pytest.raises(ValueError, match="artifact digest or size drifted"):
        module.verify_attestation(attestation_path=out, wheel_path=wheel, sdist_path=sdist)


def test_release_workflow_and_manual_path_share_one_preparation_command() -> None:
    workflow = (REPO_ROOT / ".github/workflows/release.yaml").read_text(encoding="utf-8")
    preparation = REPO_ROOT / "scripts/prepare-private-prerelease"

    assert preparation.is_file()
    assert "bash ./scripts/prepare-private-prerelease" in workflow
    assert "release-build-attestation.json" in preparation.read_text(encoding="utf-8")
    assert "SHA256SUMS" in preparation.read_text(encoding="utf-8")
