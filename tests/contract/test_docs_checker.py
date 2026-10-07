"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_docs_checker.py

Documentation links must resolve before a branch becomes public main.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


def checker() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "check_docs.py"
    spec = importlib.util.spec_from_file_location("motif_balance_docs_checker", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/e-south/motif-balance/blob/main/docs/missing.md",
        "https://github.com/e-south/motif-balance/tree/main/examples/missing",
        "https://raw.githubusercontent.com/e-south/motif-balance/main/assets/missing.svg",
        "https://raw.githubusercontent.com/e-south/motif-balance/"
        "0123456789abcdef0123456789abcdef01234567/assets/missing.png",
    ],
)
def test_repository_web_links_are_checked_in_current_tree(url: str) -> None:
    module = checker()
    errors = module.link_errors(module.REPO_ROOT / "README.md", f"[Guide]({url})")
    assert len(errors) == 1
    assert "broken link" in errors[0]


def test_repository_web_link_fragment_is_checked() -> None:
    module = checker()
    url = "https://github.com/e-south/motif-balance/blob/main/README.md#missing-heading"
    assert (
        "broken heading fragment"
        in module.link_errors(module.REPO_ROOT / "README.md", f"[Guide]({url})")[0]
    )


def test_valid_repository_and_external_links_are_accepted() -> None:
    module = checker()
    text = "\n".join(
        f"[Guide]({url})"
        for url in (
            "https://github.com/e-south/motif-balance/blob/main/examples/twelve-motifs/README.md",
            "https://github.com/e-south/motif-balance/tree/main/examples/twelve-motifs/",
            "https://raw.githubusercontent.com/e-south/motif-balance/main/assets/motif-balance-banner.svg",
            "https://github.com/another/project/blob/main/README.md",
        )
    )
    assert module.link_errors(module.REPO_ROOT / "README.md", text) == []


@pytest.mark.parametrize(
    "html",
    [
        '<img src="missing.png" width="640" alt="Example">',
        '<a href="missing.mp4">Watch the example</a>',
    ],
)
def test_html_preview_links_are_checked(html: str) -> None:
    module = checker()
    errors = module.link_errors(module.REPO_ROOT / "README.md", html)
    assert len(errors) == 1
    assert "broken link" in errors[0]


@pytest.mark.parametrize(
    "text",
    [
        "![Banner](assets/banner.png)",
        "[Guide](docs/README.md)",
        '<img src="examples/candidate.png" alt="Candidate">',
        "![Banner](http://example.org/banner.png)",
    ],
)
def test_package_description_rejects_relative_or_insecure_links(text: str) -> None:
    assert checker().package_description_errors(text)


def test_package_description_accepts_https_links_and_local_anchors() -> None:
    text = (
        "![Banner](https://example.org/banner.png)\n"
        "[Guide](https://example.org/docs)\n[Install](#install)"
    )
    assert checker().package_description_errors(text) == []


@pytest.mark.parametrize("target", ["relative.md", "http://example.org/guide"])
def test_linked_image_requires_https_for_the_enclosing_link(target: str) -> None:
    text = f"[![Badge](https://example.org/badge.svg)]({target})"
    errors = checker().package_description_errors(text)
    assert len(errors) == 1
    assert target in errors[0]


def test_linked_image_accepts_https_for_both_destinations() -> None:
    text = "[![Badge](https://example.org/badge.svg)](https://example.org/guide)"
    assert checker().package_description_errors(text) == []


def test_linked_image_checks_the_enclosing_repository_link() -> None:
    module = checker()
    text = "[![Badge](https://example.org/badge.svg)](docs/missing.md)"
    errors = module.link_errors(module.REPO_ROOT / "README.md", text)
    assert len(errors) == 1
    assert "broken link 'docs/missing.md'" in errors[0]


@pytest.fixture
def pinned_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[ModuleType, str]:
    module = checker()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    (tmp_path / "guide.md").write_text("# Historical heading\n")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "image.png").write_bytes(b"image")
    (tmp_path / "historical.png").write_bytes(b"historical image")
    with (tmp_path / "large.gif").open("wb") as stream:
        stream.truncate(10_000_001)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Documentation Test",
            "-c",
            "user.email=docs@example.invalid",
            "commit",
            "--quiet",
            "--no-gpg-sign",
            "-m",
            "historical fixtures",
        ],
        cwd=tmp_path,
        check=True,
    )
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True
    ).strip()
    (tmp_path / "guide.md").write_text("# Current heading\n")
    (tmp_path / "historical.png").unlink()
    (tmp_path / "new.png").write_bytes(b"new image")
    (tmp_path / "large.gif").write_bytes(b"small image now")
    return module, revision


@pytest.mark.parametrize("pinned", [False, True])
def test_raw_repository_link_rejects_a_directory(pinned_repository, pinned) -> None:
    module, revision = pinned_repository
    revision = revision if pinned else "main"
    url = f"https://raw.githubusercontent.com/e-south/motif-balance/{revision}/assets"
    errors = module.link_errors(module.REPO_ROOT / "README.md", f"[Assets]({url})")
    assert len(errors) == 1 and "raw URL requires a file" in errors[0]


@pytest.mark.parametrize("pinned", [False, True])
@pytest.mark.parametrize("route, target", [("blob", "assets"), ("tree", "guide.md")])
def test_github_repository_routes_accept_file_directory_redirects(
    pinned_repository, pinned, route, target
) -> None:
    module, revision = pinned_repository
    revision = revision if pinned else "main"
    url = f"https://github.com/e-south/motif-balance/{route}/{revision}/{target}"
    assert module.link_errors(module.REPO_ROOT / "README.md", f"[Guide]({url})") == []


def test_pinned_image_cannot_borrow_a_new_file_from_the_current_checkout(pinned_repository) -> None:
    module, revision = pinned_repository
    url = f"https://raw.githubusercontent.com/e-south/motif-balance/{revision}/new.png"
    errors = module.link_errors(module.REPO_ROOT / "README.md", f"![Image]({url})")
    assert len(errors) == 1 and "broken link" in errors[0]


def test_pinned_image_remains_valid_when_deleted_from_the_current_checkout(
    pinned_repository,
) -> None:
    module, revision = pinned_repository
    url = f"https://raw.githubusercontent.com/e-south/motif-balance/{revision}/historical.png"
    assert module.link_errors(module.REPO_ROOT / "README.md", f"![Image]({url})") == []


@pytest.mark.parametrize(
    "fragment, valid", [("historical-heading", True), ("current-heading", False)]
)
def test_pinned_markdown_uses_the_historical_heading(pinned_repository, fragment, valid) -> None:
    module, revision = pinned_repository
    url = f"https://github.com/e-south/motif-balance/blob/{revision}/guide.md#{fragment}"
    errors = module.link_errors(module.REPO_ROOT / "README.md", f"[Guide]({url})")
    if valid:
        assert errors == []
    else:
        assert len(errors) == 1 and "broken heading fragment" in errors[0]


def test_pinned_image_size_uses_the_historical_bytes(pinned_repository) -> None:
    module, revision = pinned_repository
    url = f"https://raw.githubusercontent.com/e-south/motif-balance/{revision}/large.gif"
    errors = module.link_errors(module.REPO_ROOT / "README.md", f"![Image]({url})")
    assert len(errors) == 1 and "image exceeds 10 MB" in errors[0]


def test_missing_pinned_revision_does_not_fall_back_to_current_files(tmp_path, monkeypatch) -> None:
    module = checker()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    (tmp_path / "image.png").write_bytes(b"current file")
    url = "https://raw.githubusercontent.com/e-south/motif-balance/" + "0" * 40 + "/image.png"
    errors = module.link_errors(tmp_path / "README.md", f"![Image]({url})")
    assert len(errors) == 1 and "pinned revision unavailable" in errors[0]


def test_readme_rejects_images_exceeding_the_pypi_proxy_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = checker()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    image = tmp_path / "playback.gif"
    with image.open("wb") as stream:
        stream.truncate(10_000_001)
    text = "![Search](https://raw.githubusercontent.com/e-south/motif-balance/main/playback.gif)"
    errors = module.link_errors(tmp_path / "README.md", text)
    assert len(errors) == 1 and "image exceeds 10 MB" in errors[0]
    with image.open("wb") as stream:
        stream.truncate(10_000_000)
    assert module.link_errors(tmp_path / "README.md", text) == []


def test_readme_and_example_links_are_included(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = checker()
    (tmp_path / "README.md").write_text("[Missing](absent.md)")
    example = tmp_path / "examples" / "demo"
    example.mkdir(parents=True)
    (example / "README.md").write_text("[Missing](absent.md)")
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "ROOT_DOCS", [])
    module.main()
    output = capsys.readouterr().out
    assert "README.md: broken link" in output
    assert "examples/demo/README.md: broken link" in output


def test_plain_markdown_keeps_link_and_fence_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = checker()
    (tmp_path / "docs").mkdir()
    guide = tmp_path / "docs" / "guide.md"
    guide.write_text("# Read a saved result\n\nOpen its score table.\n")
    (tmp_path / "README.md").write_text(
        "# Example\n\n[Guide](https://github.com/e-south/motif-balance/blob/main/docs/guide.md)\n"
        "![Overview](https://raw.githubusercontent.com/e-south/motif-balance/main/"
        "assets/motif-balance-banner.png)\n"
    )
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "motif-balance-banner.png").touch()
    banner = assets / "motif-balance-banner.svg"
    banner.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="200" '
        'viewBox="0 0 1280 200"><title>Overview</title><desc>Design DNA</desc></svg>'
    )
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "ROOT_DOCS", [])
    monkeypatch.setattr(module, "BANNER_PATH", banner)

    assert module.main() == 0
    guide.write_text("# Read a saved result\n\n```python\nprint('incomplete')\n")
    assert module.main() == 1
    assert "unbalanced fenced code blocks" in capsys.readouterr().out
