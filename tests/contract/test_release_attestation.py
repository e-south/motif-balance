"""Contracts for immutable private-prerelease build attestations."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SUBJECT = {
    "lock_sha256": "c" * 64,
    "repository": "e-south/motif-balance",
    "revision": "a" * 40,
    "tag": "v0.2.0a1",
    "tree": "b" * 40,
    "version": "0.2.0a1",
}


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
        module.verify_attestation(
            attestation_path=out,
            wheel_path=wheel,
            sdist_path=sdist,
            expected_subject=SUBJECT,
        )
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
        module.verify_attestation(
            attestation_path=out,
            wheel_path=wheel,
            sdist_path=sdist,
            expected_subject=SUBJECT,
        )


def test_release_attestation_rejects_false_source_provenance(tmp_path: Path) -> None:
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

    with pytest.raises(ValueError, match="source provenance disagrees"):
        module.verify_attestation(
            attestation_path=out,
            wheel_path=wheel,
            sdist_path=sdist,
            expected_subject={**SUBJECT, "revision": "d" * 40},
        )


def test_release_outputs_reject_dangling_symlinks_and_unsafe_limitations(tmp_path: Path) -> None:
    wheel = tmp_path / "motif_balance-0.2.0a1-py3-none-any.whl"
    sdist = tmp_path / "motif_balance-0.2.0a1.tar.gz"
    wheel.write_bytes(b"wheel-bytes")
    sdist.write_bytes(b"sdist-bytes")
    target = tmp_path / "outside.json"
    out = tmp_path / "release-build-attestation.json"
    out.symlink_to(target)
    module = _module()

    with pytest.raises(ValueError, match="refusing to overwrite attestation"):
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
    assert not target.exists()

    out.unlink()
    with pytest.raises(ValueError, match="limitations"):
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
            limitations=["private/secret/path"],
        )

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
    checksum_target = tmp_path / "outside-checksums.txt"
    (tmp_path / "SHA256SUMS").symlink_to(checksum_target)
    with pytest.raises(ValueError, match="refusing to overwrite SHA256SUMS"):
        module.write_checksum_manifest(tmp_path)
    assert not checksum_target.exists()


def test_release_directory_rejects_extra_entries(tmp_path: Path) -> None:
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
    module.write_checksum_manifest(tmp_path)
    (tmp_path / "extra").mkdir()

    with pytest.raises(ValueError, match="release directory entries drifted"):
        module.verify_release_directory(tmp_path, expected_subject=SUBJECT)


def test_release_workflow_and_manual_path_share_one_preparation_command() -> None:
    workflow = (REPO_ROOT / ".github/workflows/release.yaml").read_text(encoding="utf-8")
    preparation = REPO_ROOT / "scripts/prepare-private-prerelease"

    assert preparation.is_file()
    assert "bash ./scripts/prepare-private-prerelease" in workflow
    assert "gh release create" not in workflow
    assert "release-build-attestation.json" in preparation.read_text(encoding="utf-8")
    assert "SHA256SUMS" in preparation.read_text(encoding="utf-8")
