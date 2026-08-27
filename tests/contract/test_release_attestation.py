"""Contracts for immutable prerelease build attestations."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SUBJECT = {
    "lock_sha256": "c" * 64,
    "repository": "e-south/motif-balance",
    "revision": "a" * 40,
    "tag": "v0.2.0a3",
    "tree": "b" * 40,
    "version": "0.2.0a3",
}


def _module() -> ModuleType:
    path = REPO_ROOT / "scripts/release_attestation.py"
    spec = importlib.util.spec_from_file_location("motif_balance_release_attestation", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_attestation_is_canonical_and_binds_exact_artifacts(tmp_path: Path) -> None:
    wheel = tmp_path / "motif_balance-0.2.0a3-py3-none-any.whl"
    sdist = tmp_path / "motif_balance-0.2.0a3.tar.gz"
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
        tag="v0.2.0a3",
        version="0.2.0a3",
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
    wheel = tmp_path / "motif_balance-0.2.0a3-py3-none-any.whl"
    sdist = tmp_path / "motif_balance-0.2.0a3.tar.gz"
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
        tag="v0.2.0a3",
        version="0.2.0a3",
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
    wheel = tmp_path / "motif_balance-0.2.0a3-py3-none-any.whl"
    sdist = tmp_path / "motif_balance-0.2.0a3.tar.gz"
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
        tag="v0.2.0a3",
        version="0.2.0a3",
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
    wheel = tmp_path / "motif_balance-0.2.0a3-py3-none-any.whl"
    sdist = tmp_path / "motif_balance-0.2.0a3.tar.gz"
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
            tag="v0.2.0a3",
            version="0.2.0a3",
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
            tag="v0.2.0a3",
            version="0.2.0a3",
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
        tag="v0.2.0a3",
        version="0.2.0a3",
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
    wheel = tmp_path / "motif_balance-0.2.0a3-py3-none-any.whl"
    sdist = tmp_path / "motif_balance-0.2.0a3.tar.gz"
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
        tag="v0.2.0a3",
        version="0.2.0a3",
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


def test_repository_subject_rejects_dirty_source_and_lightweight_tag(tmp_path: Path) -> None:
    module = _module()
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Release Test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "release-test@example.invalid"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "motif-balance"\nversion = "0.2.0a3"\n',
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "pyproject.toml", "uv.lock"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=tmp_path, check=True)

    expected = module.subject_from_repository(tmp_path, require_tag=False)
    (tmp_path / "uv.lock").write_text("version = 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source repository is not clean"):
        module.subject_from_repository(tmp_path, require_tag=False)
    subprocess.run(["git", "restore", "uv.lock"], cwd=tmp_path, check=True)

    subprocess.run(["git", "tag", "v0.2.0a3"], cwd=tmp_path, check=True)
    with pytest.raises(ValueError, match="annotated tag object"):
        module.subject_from_repository(tmp_path, require_tag=True)
    subprocess.run(["git", "tag", "-d", "v0.2.0a3"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "tag", "-a", "v0.2.0a3", "-m", "release fixture"],
        cwd=tmp_path,
        check=True,
    )
    assert module.subject_from_repository(tmp_path, require_tag=True) == expected


def test_release_workflow_and_manual_path_share_one_preparation_command() -> None:
    workflow = (REPO_ROOT / ".github/workflows/release.yaml").read_text(encoding="utf-8")
    preparation = REPO_ROOT / "scripts/prepare-prerelease"

    assert preparation.is_file()
    assert "bash ./scripts/prepare-prerelease" in workflow
    assert '--out "${RUNNER_TEMP}/motif-balance-dist"' in workflow
    assert "path: ${{ runner.temp }}/motif-balance-dist/" in workflow
    assert "gh release create" not in workflow
    preparation_text = preparation.read_text(encoding="utf-8")
    release_revision = preparation_text.index('release_revision="$(git rev-parse HEAD)"')
    verification = preparation_text.index("bash ./scripts/agent-verify")
    archive = preparation_text.index('git archive --format=tar "$release_revision"')
    output_creation = preparation_text.index('mkdir -- "$out_dir"')
    assert release_revision < verification < archive
    assert output_creation < verification
    assert 'mkdir -p "$out_dir"' not in preparation_text
    assert '--expected-revision "$release_revision"' in preparation_text
    assert "uv run --locked python -c" in preparation_text
    assert "import subprocess,sys,tomllib" not in preparation_text
    assert 'uv build --no-sources --out-dir "$build_root"' in preparation_text
    assert 'uv build --no-sources --out-dir "$out_dir"' not in preparation_text
    assert 'cp -p -n -- "$artifact" "$target"' in preparation_text
    assert "release-build-attestation.json" in preparation_text
    assert "SHA256SUMS" in preparation_text


def test_release_preparation_rejects_relative_output_before_build() -> None:
    completed = subprocess.run(
        [
            "bash",
            "./scripts/prepare-prerelease",
            "--out",
            "dist-release",
            "--builder-kind",
            "maintainer_local",
            "--limitation",
            "independent_rebuild_not_performed",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "absolute path outside the repository" in completed.stderr
