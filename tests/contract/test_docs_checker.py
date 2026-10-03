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
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="230" '
        'viewBox="0 0 1280 230"><title>Overview</title><desc>Design DNA</desc></svg>'
    )
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "ROOT_DOCS", [])
    monkeypatch.setattr(module, "BANNER_PATH", banner)

    assert module.main() == 0
    guide.write_text("# Read a saved result\n\n```python\nprint('incomplete')\n")
    assert module.main() == 1
    assert "unbalanced fenced code blocks" in capsys.readouterr().out
