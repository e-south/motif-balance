"""Static contracts for the public-repository prerelease workflow."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_release_ancestry_check_uses_prefetched_main() -> None:
    """Credential-free checkout must not perform a later authenticated fetch."""
    workflow = (REPO_ROOT / ".github/workflows/release.yaml").read_text(encoding="utf-8")

    assert "persist-credentials: false" in workflow
    assert "fetch-depth: 0" in workflow
    assert "git fetch origin main" not in workflow
    assert 'git merge-base --is-ancestor "${GITHUB_SHA}" origin/main' in workflow


def test_release_version_check_accepts_only_numbered_prereleases() -> None:
    """An incidental a, b, or rc substring must not satisfy the release gate."""
    workflow = (REPO_ROOT / ".github/workflows/release.yaml").read_text(encoding="utf-8")

    assert 're.fullmatch(r"[0-9]+(?:\\.[0-9]+){2}(?:a|b|rc)[0-9]+", version)' in workflow
    assert 'case "$project_version" in' not in workflow


def test_release_requires_public_repository_without_package_publication() -> None:
    workflow = (REPO_ROOT / ".github/workflows/release.yaml").read_text(encoding="utf-8")

    assert 'test "${{ github.event.repository.visibility }}" = "public"' in workflow
    assert 'test "${{ github.event.repository.visibility }}" = "private"' not in workflow
    assert "gh release create" not in workflow
    assert "pypa/gh-action-pypi-publish" not in workflow
