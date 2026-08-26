#!/usr/bin/env python3
"""Reject obvious private or credential-bearing repository content."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
TEXT_LIMIT = 2_000_000
PATTERNS = {
    "absolute user path": re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+/"),
    "private key material": re.compile("-----BEGIN " + "(?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile("gh" + "[pousr]_[A-Za-z0-9]{20,}"),
    "AWS access key": re.compile("AK" + "IA[0-9A-Z]{16}"),
    "OpenAI secret": re.compile("sk-" + "(?:proj-)?[A-Za-z0-9_-]{20,}"),
}


def candidate_paths() -> list[Path]:
    """Return tracked and unignored candidate files."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    return [REPO_ROOT / raw.decode() for raw in result.stdout.split(b"\0") if raw]


def main() -> int:
    """Check content and the explicit package publication brake."""
    errors: list[str] = []
    for path in candidate_paths():
        if path.is_symlink():
            errors.append(f"{path.relative_to(REPO_ROOT)}: tracked or candidate symlink")
            continue
        if not path.is_file() or path.resolve() == SELF or path.stat().st_size > TEXT_LIMIT:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                errors.append(f"{path.relative_to(REPO_ROOT)}: contains {label}")

    project_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    brake = "Private :: Do Not Upload"
    if brake not in project_text:
        errors.append("pyproject.toml: missing private publication brake")

    release_path = REPO_ROOT / ".github" / "workflows" / "release.yaml"
    if release_path.exists():
        release_text = release_path.read_text(encoding="utf-8").lower()
        forbidden_release_terms = ("pypa/gh-action-pypi-publish", "uv publish", "id-token: write")
        for term in forbidden_release_terms:
            if term in release_text:
                errors.append(f"release workflow enables forbidden publication seam: {term}")

    if errors:
        print("Public-safety failures:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Public safety: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
