#!/usr/bin/env python3
"""Create and verify immutable Motif Balance private-release attestations."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any

SCHEMA = "motif-balance.release-build-attestation/v1"
REPOSITORY = "e-south/motif-balance"
ATTESTATION_NAME = "release-build-attestation.json"
CHECKSUM_NAME = "SHA256SUMS"
VERSION_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]+){2}(?:a|b|rc)[0-9]+")
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
LIMITATION_PATTERN = re.compile(r"[a-z0-9][a-z0-9_.-]{0,127}")
BUILDER_KINDS = {"github_actions", "maintainer_local"}
VERIFICATION = [
    {"gate": "agent_verify", "status": "pass"},
    {"gate": "exact_distribution_smoke", "status": "pass"},
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _artifact(path: Path, *, kind: str) -> dict[str, object]:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{kind} must be a regular file")
    return {
        "bytes": path.stat().st_size,
        "kind": kind,
        "name": path.name,
        "sha256": _sha256(path),
    }


def _canonical(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def _require_text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value or any(character in value for character in "\r\n\0"):
        raise ValueError(f"{label} must be nonempty single-line text")
    return value


def _require_hex(value: object, *, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"{label} has an invalid digest or revision")
    return value


def _validate_payload(payload: dict[str, Any]) -> None:
    if set(payload) != {"artifacts", "builder", "limitations", "schema", "subject", "verification"}:
        raise ValueError("attestation top-level fields drifted")
    if payload.get("schema") != SCHEMA:
        raise ValueError("unexpected release-build attestation schema")

    subject = payload.get("subject")
    if not isinstance(subject, dict) or set(subject) != {
        "lock_sha256",
        "repository",
        "revision",
        "tag",
        "tree",
        "version",
    }:
        raise ValueError("attestation subject fields drifted")
    version = _require_text(subject["version"], label="subject.version")
    if VERSION_PATTERN.fullmatch(version) is None or subject["tag"] != f"v{version}":
        raise ValueError("attestation version and tag disagree")
    if subject["repository"] != REPOSITORY:
        raise ValueError("unexpected release repository")
    _require_hex(subject["revision"], pattern=HEX40, label="subject.revision")
    _require_hex(subject["tree"], pattern=HEX40, label="subject.tree")
    _require_hex(subject["lock_sha256"], pattern=HEX64, label="subject.lock_sha256")

    builder = payload.get("builder")
    if not isinstance(builder, dict) or set(builder) != {
        "architecture",
        "kind",
        "operating_system",
        "python_version",
        "source_date_epoch",
        "uv_version",
    }:
        raise ValueError("attestation builder fields drifted")
    if builder["kind"] not in BUILDER_KINDS:
        raise ValueError("unsupported builder kind")
    for key in ("architecture", "operating_system", "python_version", "uv_version"):
        _require_text(builder[key], label=f"builder.{key}")
    epoch = builder["source_date_epoch"]
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
        raise ValueError("builder.source_date_epoch must be a nonnegative integer")

    if payload.get("verification") != VERIFICATION:
        raise ValueError("release verification gates drifted")
    limitations = payload.get("limitations")
    if (
        not isinstance(limitations, list)
        or not limitations
        or limitations != sorted(set(limitations))
        or any(
            not isinstance(item, str) or LIMITATION_PATTERN.fullmatch(item) is None
            for item in limitations
        )
    ):
        raise ValueError("limitations must be sorted unique safe tokens")

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 2:
        raise ValueError("attestation must contain exactly one wheel and one sdist")
    expected_names = {
        "sdist": f"motif_balance-{version}.tar.gz",
        "wheel": f"motif_balance-{version}-py3-none-any.whl",
    }
    observed_kinds = [artifact.get("kind") for artifact in artifacts if isinstance(artifact, dict)]
    if observed_kinds != ["sdist", "wheel"]:
        raise ValueError("attestation artifact order or kinds drifted")
    for artifact in artifacts:
        if not isinstance(artifact, dict) or set(artifact) != {"bytes", "kind", "name", "sha256"}:
            raise ValueError("attestation artifact fields drifted")
        kind = artifact["kind"]
        if artifact["name"] != expected_names[kind]:
            raise ValueError("attestation artifact name disagrees with the release version")
        size = artifact["bytes"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 1:
            raise ValueError("attestation artifact size must be positive")
        _require_hex(artifact["sha256"], pattern=HEX64, label=f"artifacts.{kind}.sha256")


def write_attestation(
    *,
    out_path: Path,
    wheel_path: Path,
    sdist_path: Path,
    repository: str,
    revision: str,
    tree: str,
    tag: str,
    version: str,
    lock_sha256: str,
    builder_kind: str,
    python_version: str,
    uv_version: str,
    operating_system: str,
    architecture: str,
    source_date_epoch: int,
    limitations: list[str],
) -> str:
    """Write one canonical attestation and return its content digest."""
    if out_path.exists() or out_path.is_symlink():
        raise ValueError(f"refusing to overwrite attestation: {out_path.name}")
    payload: dict[str, object] = {
        "artifacts": sorted(
            [_artifact(wheel_path, kind="wheel"), _artifact(sdist_path, kind="sdist")],
            key=lambda item: str(item["kind"]),
        ),
        "builder": {
            "architecture": architecture,
            "kind": builder_kind,
            "operating_system": operating_system,
            "python_version": python_version,
            "source_date_epoch": source_date_epoch,
            "uv_version": uv_version,
        },
        "limitations": sorted(set(limitations)),
        "schema": SCHEMA,
        "subject": {
            "lock_sha256": lock_sha256,
            "repository": repository,
            "revision": revision,
            "tag": tag,
            "tree": tree,
            "version": version,
        },
        "verification": VERIFICATION,
    }
    _validate_payload(payload)
    raw = _canonical(payload)
    with out_path.open("xb") as handle:
        handle.write(raw)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def verify_attestation(
    *,
    attestation_path: Path,
    wheel_path: Path,
    sdist_path: Path,
    expected_subject: dict[str, str],
) -> str:
    """Verify canonical bytes, schema, and both exact release artifacts."""
    if not attestation_path.is_file() or attestation_path.is_symlink():
        raise ValueError("attestation must be a regular file")
    raw = attestation_path.read_bytes()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("attestation must be a JSON object")
    if raw != _canonical(payload):
        raise ValueError("attestation is not canonical sorted JSON")
    _validate_payload(payload)
    if payload["subject"] != expected_subject:
        raise ValueError("source provenance disagrees with expected tagged source")
    observed = {
        "sdist": _artifact(sdist_path, kind="sdist"),
        "wheel": _artifact(wheel_path, kind="wheel"),
    }
    for expected in payload["artifacts"]:
        if expected != observed[expected["kind"]]:
            raise ValueError(f"artifact digest or size drifted: {expected['kind']}")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _release_files(directory: Path) -> tuple[Path, Path, Path]:
    wheels = list(directory.glob("*.whl"))
    sdists = list(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("release directory must contain exactly one wheel and one sdist")
    return wheels[0], sdists[0], directory / ATTESTATION_NAME


def _require_exact_entries(directory: Path, expected_names: set[str]) -> None:
    entries = list(directory.iterdir())
    if {entry.name for entry in entries} != expected_names or any(
        not entry.is_file() or entry.is_symlink() for entry in entries
    ):
        raise ValueError("release directory entries drifted")


def write_checksum_manifest(directory: Path) -> None:
    """Write checksums over the wheel, sdist, and build attestation."""
    wheel, sdist, attestation = _release_files(directory)
    checksum_path = directory / CHECKSUM_NAME
    if checksum_path.exists() or checksum_path.is_symlink():
        raise ValueError("refusing to overwrite SHA256SUMS")
    expected_names = {wheel.name, sdist.name, ATTESTATION_NAME}
    _require_exact_entries(directory, expected_names)
    if not attestation.is_file() or attestation.is_symlink():
        raise ValueError("release directory is missing the build attestation")
    assets = sorted((wheel, sdist, attestation), key=lambda path: path.name)
    with checksum_path.open("x", encoding="utf-8") as handle:
        handle.write("".join(f"{_sha256(path)}  {path.name}\n" for path in assets))


def verify_release_directory(directory: Path, *, expected_subject: dict[str, str]) -> str:
    """Verify the exact four-file release directory and return attestation digest."""
    wheel, sdist, attestation = _release_files(directory)
    expected_names = {wheel.name, sdist.name, ATTESTATION_NAME, CHECKSUM_NAME}
    _require_exact_entries(directory, expected_names)
    checksum_lines = (directory / CHECKSUM_NAME).read_text(encoding="utf-8").splitlines()
    expected_lines = [
        f"{_sha256(path)}  {path.name}"
        for path in sorted((wheel, sdist, attestation), key=lambda path: path.name)
    ]
    if checksum_lines != expected_lines:
        raise ValueError("SHA256SUMS disagrees with release assets")
    return verify_attestation(
        attestation_path=attestation,
        wheel_path=wheel,
        sdist_path=sdist,
        expected_subject=expected_subject,
    )


def _git(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _git_bytes(repo_root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
    ).stdout


def subject_from_repository(repo_root: Path, *, require_tag: bool) -> dict[str, str]:
    """Resolve the expected release subject from an exact source checkout."""
    if _git(repo_root, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("source repository is not clean")
    project = tomllib.loads(_git_bytes(repo_root, "show", "HEAD:pyproject.toml").decode())[
        "project"
    ]
    version = str(project["version"])
    revision = _git(repo_root, "rev-parse", "HEAD")
    tag = f"v{version}"
    if require_tag:
        if _git(repo_root, "cat-file", "-t", f"refs/tags/{tag}") != "tag":
            raise ValueError("release tag must be an annotated tag object")
        tagged_revision = _git(repo_root, "rev-parse", f"refs/tags/{tag}^{{commit}}")
        if tagged_revision != revision:
            raise ValueError("release tag does not point to the expected source revision")
    return {
        "lock_sha256": _sha256_bytes(_git_bytes(repo_root, "show", "HEAD:uv.lock")),
        "repository": REPOSITORY,
        "revision": revision,
        "tag": tag,
        "tree": _git(repo_root, "rev-parse", "HEAD^{tree}"),
        "version": version,
    }


def _create_command(args: argparse.Namespace) -> int:
    directory = args.directory.resolve()
    repo_root = Path(__file__).resolve().parents[1]
    wheel, sdist, attestation = _release_files(directory)
    subject = subject_from_repository(repo_root, require_tag=False)
    uv_version = subprocess.run(
        ["uv", "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    digest = write_attestation(
        out_path=attestation,
        wheel_path=wheel,
        sdist_path=sdist,
        repository=REPOSITORY,
        revision=subject["revision"],
        tree=subject["tree"],
        tag=subject["tag"],
        version=subject["version"],
        lock_sha256=subject["lock_sha256"],
        builder_kind=args.builder_kind,
        python_version=platform.python_version(),
        uv_version=uv_version,
        operating_system=platform.system(),
        architecture=platform.machine(),
        source_date_epoch=args.source_date_epoch,
        limitations=args.limitation,
    )
    write_checksum_manifest(directory)
    verify_release_directory(directory, expected_subject=subject)
    print(digest)
    return 0


def _verify_command(args: argparse.Namespace) -> int:
    expected_subject = subject_from_repository(
        args.repository_root.resolve(),
        require_tag=args.require_tag,
    )
    print(
        verify_release_directory(
            args.directory.resolve(),
            expected_subject=expected_subject,
        )
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="create attestation and checksums")
    create.add_argument("--directory", type=Path, required=True)
    create.add_argument("--builder-kind", choices=sorted(BUILDER_KINDS), required=True)
    create.add_argument("--source-date-epoch", type=int, required=True)
    create.add_argument("--limitation", action="append", required=True)
    create.set_defaults(handler=_create_command)
    verify = commands.add_parser("verify", help="verify one release directory")
    verify.add_argument("--directory", type=Path, required=True)
    verify.add_argument("--repository-root", type=Path, required=True)
    verify.add_argument("--require-tag", action="store_true")
    verify.set_defaults(handler=_verify_command)
    return parser


def main() -> int:
    args = _parser().parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
