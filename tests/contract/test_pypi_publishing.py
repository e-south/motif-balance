# -----------------------------------------------------------------------------
# motif-balance
# tests/contract/test_pypi_publishing.py
#
# Check that publishing requires reviewed release files and isolated credentials.
#
# Author: Eric J. South, Dunlop Lab
# -----------------------------------------------------------------------------
"""Contracts for the manual PyPI publishing boundary."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _workflow() -> dict:
    # BaseLoader keeps the YAML key `on` as text, matching GitHub's interpretation.
    return yaml.load((ROOT / ".github/workflows/publish.yaml").read_text(), Loader=yaml.BaseLoader)


def test_pypi_upload_requires_manual_dispatch_and_a_protected_job() -> None:
    workflow = _workflow()
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    jobs = workflow["jobs"]
    assert "permissions" not in jobs["verify"]
    publish = jobs["publish"]
    assert publish["needs"] == "verify"
    assert publish["environment"]["name"] == "pypi"
    assert publish["permissions"] == {"id-token": "write"}
    assert all("run" not in step for step in publish["steps"])
    assert "checkout" not in str(publish["steps"])


def test_pypi_upload_uses_verified_files_without_rebuilding() -> None:
    workflow = _workflow()
    jobs = workflow["jobs"]
    verification = "\n".join(step.get("run", "") for step in jobs["verify"]["steps"])
    assert 'git cat-file -t "refs/tags/$RELEASE_TAG"' in verification
    assert "git merge-base --is-ancestor HEAD origin/main" in verification
    assert "gh release download" in verification
    assert "scripts/release_attestation.py verify" in verification
    assert "--require-tag" in verification
    assert "scripts/wheel-smoke" in verification
    assert "uv build" not in verification
    upload = jobs["verify"]["steps"][-1]
    download = jobs["publish"]["steps"][0]
    assert upload["with"]["name"] == download["with"]["name"]
    assert "pypi-distributions" in upload["with"]["path"]
    for job in jobs.values():
        for step in job["steps"]:
            if "uses" in step:
                revision = step["uses"].split("@", 1)[1]
                assert len(revision) == 40 and all(c in "0123456789abcdef" for c in revision)
